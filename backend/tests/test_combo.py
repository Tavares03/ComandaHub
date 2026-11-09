"""Combo dentro do item: grupos que so aparecem quando o cliente escolhe "Fazer combo"."""
from __future__ import annotations

import random
from decimal import Decimal
from uuid import uuid4

from app.models.catalog import Product, ProductOption, ProductOptionGroup
from app.services.option_picker import pick_option_ids

API = "/api/v1/establishments"


def _establishment(client, headers, name="Burger Station"):
    return next(e for e in client.get(API, headers=headers).json() if e["name"] == name)


def _category_id(client, headers, establishment_id):
    return client.get(f"{API}/{establishment_id}/categories", headers=headers).json()[0]["id"]


def _create(client, headers, establishment_id, groups, price="30.00", name=None):
    payload = {
        "category_id": _category_id(client, headers, establishment_id),
        "name": name or f"Teste {uuid4().hex[:8]}",
        "price": price,
        "option_groups": groups,
    }
    return client.post(f"{API}/{establishment_id}/products", headers=headers, json=payload)


def _product(client, headers, establishment_id, groups=(), price="30.00", name=None):
    response = _create(client, headers, establishment_id, list(groups), price, name)
    assert response.status_code == 201, response.text
    return response.json()


def _option(product, group_name, option_name):
    group = next(g for g in product["option_groups"] if g["name"] == group_name)
    return next(o for o in group["options"] if o["name"] == option_name)


def _order(client, headers, establishment_id, product_id, option_ids):
    payload = {
        "fulfillment_type": "COUNTER",
        "payment_method": "CASH",
        "items": [{"product_id": product_id, "quantity": 1, "options": [{"option_id": oid} for oid in option_ids]}],
    }
    return client.post(f"{API}/{establishment_id}/orders", headers=headers, json=payload)


def combo_groups(side_extra="0.00", side_link=None, drink_link=None):
    return [
        {"name": "Combo", "min_choices": 0, "max_choices": 1,
         "options": [{"name": "Fazer combo", "price_delta": "18.00"}]},
        {"name": "Acompanhamento do combo", "min_choices": 1, "max_choices": 1, "depends_on": {"group": 0, "option": 0},
         "options": [{"name": "Fritas", "price_delta": "0.00", "linked_product_id": side_link},
                     {"name": "Aneis", "price_delta": side_extra}]},
        {"name": "Bebida do combo", "min_choices": 1, "max_choices": 1, "depends_on": {"group": 0, "option": 0},
         "options": [{"name": "Refri", "price_delta": "0.00", "linked_product_id": drink_link}]},
    ]


def test_burger_without_combo_does_not_require_side_or_drink(client, auth_headers):
    est = _establishment(client, auth_headers)
    burger = _product(client, auth_headers, est["id"], combo_groups())

    response = _order(client, auth_headers, est["id"], burger["id"], [])

    assert response.status_code == 201, response.text
    assert Decimal(response.json()["items"][0]["unit_price"]) == Decimal("30.00")


def test_combo_requires_side_and_drink(client, auth_headers):
    est = _establishment(client, auth_headers)
    burger = _product(client, auth_headers, est["id"], combo_groups())

    response = _order(client, auth_headers, est["id"], burger["id"], [_option(burger, "Combo", "Fazer combo")["id"]])

    assert response.status_code == 422
    assert "Acompanhamento do combo" in response.json()["detail"]


def test_combo_side_cannot_be_chosen_without_combo(client, auth_headers):
    est = _establishment(client, auth_headers)
    burger = _product(client, auth_headers, est["id"], combo_groups())

    picks = [_option(burger, "Acompanhamento do combo", "Fritas")["id"], _option(burger, "Bebida do combo", "Refri")["id"]]

    response = _order(client, auth_headers, est["id"], burger["id"], picks)

    assert response.status_code == 422
    assert "Fazer combo" in response.json()["detail"]


def test_combo_price_is_burger_plus_combo_plus_side_upgrade(client, auth_headers):
    est = _establishment(client, auth_headers)
    burger = _product(client, auth_headers, est["id"], combo_groups(side_extra="4.00"))
    picks = [
        _option(burger, "Combo", "Fazer combo")["id"],
        _option(burger, "Acompanhamento do combo", "Aneis")["id"],
        _option(burger, "Bebida do combo", "Refri")["id"],
    ]

    response = _order(client, auth_headers, est["id"], burger["id"], picks)

    assert response.status_code == 201, response.text
    # 30,00 + 18,00 (combo) + 4,00 (troca por aneis) + 0,00 (refri)
    assert Decimal(response.json()["items"][0]["unit_price"]) == Decimal("52.00")


def test_group_cannot_depend_on_option_of_a_later_group(client, auth_headers):
    est = _establishment(client, auth_headers)
    groups = [
        {"name": "Bebida do combo", "min_choices": 1, "max_choices": 1, "depends_on": {"group": 1, "option": 0},
         "options": [{"name": "Refri", "price_delta": "0.00"}]},
        {"name": "Combo", "min_choices": 0, "max_choices": 1, "options": [{"name": "Fazer combo", "price_delta": "18.00"}]},
    ]

    response = _create(client, auth_headers, est["id"], groups)

    assert response.status_code == 422


def test_combo_option_links_to_real_product(client, auth_headers):
    est = _establishment(client, auth_headers)
    fries = _product(client, auth_headers, est["id"], price="16.90")
    burger = _product(client, auth_headers, est["id"], combo_groups(side_link=fries["id"]))

    assert _option(burger, "Acompanhamento do combo", "Fritas")["linked_product_id"] == fries["id"]
    combo = _option(burger, "Combo", "Fazer combo")
    side_group = next(g for g in burger["option_groups"] if g["name"] == "Acompanhamento do combo")
    assert side_group["depends_on_option_id"] == combo["id"]


def test_option_cannot_link_to_product_of_another_store(client, auth_headers):
    burger_station = _establishment(client, auth_headers)
    smash_house = _establishment(client, auth_headers, "Smash House")
    foreign_fries = _product(client, auth_headers, smash_house["id"], price="16.90")

    response = _create(client, auth_headers, burger_station["id"], combo_groups(side_link=foreign_fries["id"]))

    assert response.status_code == 422


def test_saving_with_ids_keeps_option_ids_and_dependency(client, auth_headers):
    est = _establishment(client, auth_headers)
    burger = _product(client, auth_headers, est["id"], combo_groups())
    groups = [
        {
            "id": group["id"],
            "name": group["name"],
            "min_choices": group["min_choices"],
            "max_choices": group["max_choices"],
            "depends_on": {"group": 0, "option": 0} if group["depends_on_option_id"] else None,
            "options": [{"id": o["id"], "name": o["name"], "price_delta": o["price_delta"]} for o in group["options"]],
        }
        for group in burger["option_groups"]
    ]

    response = client.patch(f"{API}/{est['id']}/products/{burger['id']}", headers=auth_headers, json={"option_groups": groups})

    assert response.status_code == 200, response.text
    saved = response.json()
    assert _option(saved, "Combo", "Fazer combo")["id"] == _option(burger, "Combo", "Fazer combo")["id"]
    assert _option(saved, "Bebida do combo", "Refri")["id"] == _option(burger, "Bebida do combo", "Refri")["id"]
    drink_group = next(g for g in saved["option_groups"] if g["name"] == "Bebida do combo")
    assert drink_group["depends_on_option_id"] == _option(burger, "Combo", "Fazer combo")["id"]


def test_seeded_burgers_offer_combo_with_real_sides_and_drinks(client, auth_headers):
    est = _establishment(client, auth_headers)
    products = client.get(f"{API}/{est['id']}/products", headers=auth_headers).json()
    by_name = {product["name"]: product for product in products}
    smash = by_name["Smash Burger"]

    side_group = next(g for g in smash["option_groups"] if g["name"] == "Acompanhamento do combo")
    drink_group = next(g for g in smash["option_groups"] if g["name"] == "Bebida do combo")
    combo_group = next(g for g in smash["option_groups"] if g["name"] == "Combo")
    assert side_group["depends_on_option_id"] == combo_group["options"][0]["id"]
    assert drink_group["depends_on_option_id"] == combo_group["options"][0]["id"]
    assert {o["linked_product_id"] for o in side_group["options"]} >= {by_name["Batata Frita"]["id"]}
    assert {o["linked_product_id"] for o in drink_group["options"]} >= {by_name["Coca-Cola"]["id"]}


# ------------------------------------------------------------------ simulador


def _memory_product() -> Product:
    combo = ProductOption(id="combo", name="Fazer combo", price_delta=Decimal("18"), is_available=True, paused_channels=[])
    product = Product(id="p", name="Burger", price=Decimal("30"), is_available=True, paused_channels=[])
    product.option_groups = [
        ProductOptionGroup(id="g-combo", name="Combo", min_choices=0, max_choices=1, allow_repeat=False, options=[combo]),
        ProductOptionGroup(
            id="g-side", name="Acompanhamento do combo", min_choices=1, max_choices=1, allow_repeat=False,
            depends_on_option_id="combo",
            options=[ProductOption(id="fries", name="Fritas", price_delta=Decimal("0"), is_available=True, paused_channels=[])],
        ),
    ]
    return product


def test_simulator_only_picks_combo_side_when_combo_is_picked():
    product = _memory_product()
    seen_with_combo = seen_without_combo = False
    for seed in range(60):
        picked = pick_option_ids(product, random.Random(seed), extra_chance=0.5)
        if "combo" in picked:
            seen_with_combo = True
            assert "fries" in picked
        else:
            seen_without_combo = True
            assert "fries" not in picked
    assert seen_with_combo and seen_without_combo
