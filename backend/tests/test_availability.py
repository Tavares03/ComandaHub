"""Pausar itens e ingredientes por canal (iFood, 99, Local), em cascata e em varias lojas."""
from __future__ import annotations

import random
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.connectors.base import NormalizedOrder, NormalizedOrderItem
from app.models.catalog import Product, ProductOption, ProductOptionGroup
from app.models.order import FulfillmentType, OrderSource, PaymentMethod, PaymentStatus
from app.services.option_picker import can_be_ordered, pick_option_ids
from app.services.order_service import create_external_order
import app.db as db_module

API = "/api/v1/establishments"


def _establishment(client, headers, name="Burger Station"):
    return next(e for e in client.get(API, headers=headers).json() if e["name"] == name)


def _category_id(client, headers, establishment_id):
    return client.get(f"{API}/{establishment_id}/categories", headers=headers).json()[0]["id"]


def _product(client, headers, establishment_id, groups=(), price="30.00", name=None, ingredients=()):
    payload = {
        "category_id": _category_id(client, headers, establishment_id),
        "name": name or f"Teste {uuid4().hex[:8]}",
        "price": price,
        "option_groups": list(groups),
        "ingredients": list(ingredients),
    }
    response = client.post(f"{API}/{establishment_id}/products", headers=headers, json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def _get_product(client, headers, establishment_id, product_id):
    products = client.get(f"{API}/{establishment_id}/products", headers=headers).json()
    return next(product for product in products if product["id"] == product_id)


def _option(product, group_name, option_name):
    group = next(g for g in product["option_groups"] if g["name"] == group_name)
    return next(o for o in group["options"] if o["name"] == option_name)


def _ingredient(client, headers, establishment_id, name):
    response = client.post(f"{API}/{establishment_id}/ingredients", headers=headers, json={"name": name})
    assert response.status_code == 201, response.text
    return response.json()


def _availability(client, headers, establishment_id, **body):
    return client.post(f"{API}/{establishment_id}/availability", headers=headers, json=body)


def _local_order(client, headers, establishment_id, product_id, option_ids=()):
    payload = {
        "fulfillment_type": "COUNTER",
        "payment_method": "CASH",
        "items": [{"product_id": product_id, "quantity": 1, "options": [{"option_id": oid} for oid in option_ids]}],
    }
    return client.post(f"{API}/{establishment_id}/orders", headers=headers, json=payload)


def _external_order(establishment_id, source, product_id, option_ids=()):
    normalized = NormalizedOrder(
        external_order_id=f"TEST-{uuid4().hex[:10]}",
        source=source,
        customer_name="Teste",
        customer_phone=None,
        delivery_address="Rua Teste, 1",
        fulfillment_type=FulfillmentType.DELIVERY,
        payment_method=PaymentMethod.ONLINE,
        payment_status=PaymentStatus.PAID,
        delivery_fee=Decimal("0.00"),
        discount=Decimal("0.00"),
        notes=None,
        items=[NormalizedOrderItem(product_id=product_id, quantity=1, option_ids=list(option_ids), notes=None)],
        raw_payload={},
    )
    # conftest troca app.db.SessionLocal pela sessao do banco de teste
    with db_module.SessionLocal() as db:
        return create_external_order(db, establishment_id, normalized)


def _combo_burger(client, headers, establishment_id, side_product_id, ingredients=()):
    groups = [
        {"name": "Combo", "min_choices": 0, "max_choices": 1, "options": [{"name": "Fazer combo", "price_delta": "18.00"}]},
        {"name": "Acompanhamento do combo", "min_choices": 1, "max_choices": 1, "depends_on": {"group": 0, "option": 0},
         "options": [{"name": "Fritas", "price_delta": "0.00", "linked_product_id": side_product_id},
                     {"name": "Aneis", "price_delta": "4.00"}]},
    ]
    return _product(client, headers, establishment_id, groups, ingredients=ingredients)


# ------------------------------------------------------------------ item por canal


def test_item_paused_on_99_is_refused_on_99_but_sold_locally(client, auth_headers):
    est = _establishment(client, auth_headers)
    fries = _product(client, auth_headers, est["id"], price="16.90")

    response = _availability(client, auth_headers, est["id"], target_type="product", target_id=fries["id"],
                             action="pause", channels=["NINETY_NINE_FOOD"], scope="item")

    assert response.status_code == 200, response.text
    assert _get_product(client, auth_headers, est["id"], fries["id"])["paused_channels"] == ["NINETY_NINE_FOOD"]
    assert _local_order(client, auth_headers, est["id"], fries["id"]).status_code == 201
    assert _external_order(est["id"], OrderSource.IFOOD, fries["id"]).items[0].product_id == fries["id"]
    with pytest.raises(HTTPException) as refused:
        _external_order(est["id"], OrderSource.NINETY_NINE_FOOD, fries["id"])
    assert refused.value.status_code == 422


def test_resuming_item_on_99_lets_99_order_it_again(client, auth_headers):
    est = _establishment(client, auth_headers)
    fries = _product(client, auth_headers, est["id"], price="16.90")
    _availability(client, auth_headers, est["id"], target_type="product", target_id=fries["id"],
                  action="pause", channels=["NINETY_NINE_FOOD", "LOCAL"], scope="item")

    _availability(client, auth_headers, est["id"], target_type="product", target_id=fries["id"],
                  action="resume", channels=["NINETY_NINE_FOOD"], scope="item")

    assert _get_product(client, auth_headers, est["id"], fries["id"])["paused_channels"] == ["LOCAL"]
    assert _external_order(est["id"], OrderSource.NINETY_NINE_FOOD, fries["id"]).items[0].product_id == fries["id"]


def test_pausing_item_everywhere_also_pauses_it_inside_combos(client, auth_headers):
    est = _establishment(client, auth_headers)
    fries = _product(client, auth_headers, est["id"], price="16.90")
    burger = _combo_burger(client, auth_headers, est["id"], fries["id"])

    response = _availability(client, auth_headers, est["id"], target_type="product", target_id=fries["id"],
                             action="pause", channels=["LOCAL"], scope="everywhere")

    assert response.status_code == 200, response.text
    burger = _get_product(client, auth_headers, est["id"], burger["id"])
    assert _option(burger, "Acompanhamento do combo", "Fritas")["paused_channels"] == ["LOCAL"]
    combo, fritas, aneis = (_option(burger, "Combo", "Fazer combo")["id"],
                            _option(burger, "Acompanhamento do combo", "Fritas")["id"],
                            _option(burger, "Acompanhamento do combo", "Aneis")["id"])
    assert _local_order(client, auth_headers, est["id"], burger["id"], [combo, fritas]).status_code == 422
    assert _local_order(client, auth_headers, est["id"], burger["id"], [combo, aneis]).status_code == 201


def test_pausing_only_the_item_keeps_it_inside_combos(client, auth_headers):
    est = _establishment(client, auth_headers)
    fries = _product(client, auth_headers, est["id"], price="16.90")
    burger = _combo_burger(client, auth_headers, est["id"], fries["id"])

    _availability(client, auth_headers, est["id"], target_type="product", target_id=fries["id"],
                  action="pause", channels=["LOCAL"], scope="item")

    burger = _get_product(client, auth_headers, est["id"], burger["id"])
    assert _option(burger, "Acompanhamento do combo", "Fritas")["paused_channels"] == []


def test_resuming_everywhere_brings_item_back_into_combos(client, auth_headers):
    est = _establishment(client, auth_headers)
    fries = _product(client, auth_headers, est["id"], price="16.90")
    burger = _combo_burger(client, auth_headers, est["id"], fries["id"])
    _availability(client, auth_headers, est["id"], target_type="product", target_id=fries["id"],
                  action="pause", channels=["IFOOD", "LOCAL"], scope="everywhere")

    _availability(client, auth_headers, est["id"], target_type="product", target_id=fries["id"],
                  action="resume", channels=["IFOOD", "LOCAL"], scope="everywhere")

    assert _get_product(client, auth_headers, est["id"], fries["id"])["paused_channels"] == []
    burger = _get_product(client, auth_headers, est["id"], burger["id"])
    assert _option(burger, "Acompanhamento do combo", "Fritas")["paused_channels"] == []


def test_dry_run_lists_affected_combos_without_changing_anything(client, auth_headers):
    est = _establishment(client, auth_headers)
    fries = _product(client, auth_headers, est["id"], price="16.90")
    burger = _combo_burger(client, auth_headers, est["id"], fries["id"])

    response = _availability(client, auth_headers, est["id"], target_type="product", target_id=fries["id"],
                             action="pause", channels=["LOCAL"], scope="everywhere", dry_run=True)

    assert response.status_code == 200, response.text
    changes = response.json()["results"][0]["changes"]
    assert {change["product_name"] for change in changes} == {fries["name"], burger["name"]}
    assert _get_product(client, auth_headers, est["id"], fries["id"])["paused_channels"] == []


def test_pausing_in_all_stores_reaches_product_with_same_name(client, auth_headers):
    burger_station = _establishment(client, auth_headers)
    smash_house = _establishment(client, auth_headers, "Smash House")
    name = f"Fritas {uuid4().hex[:6]}"
    here = _product(client, auth_headers, burger_station["id"], price="16.90", name=name)
    there = _product(client, auth_headers, smash_house["id"], price="16.90", name=name.upper())

    response = _availability(client, auth_headers, burger_station["id"], target_type="product", target_id=here["id"],
                             action="pause", channels=["IFOOD"], scope="item", all_establishments=True)

    assert response.status_code == 200, response.text
    assert _get_product(client, auth_headers, smash_house["id"], there["id"])["paused_channels"] == ["IFOOD"]
    assert "Pizzaria Bella Massa" in response.json()["not_found_in"]


def test_unknown_channel_is_rejected(client, auth_headers):
    est = _establishment(client, auth_headers)
    fries = _product(client, auth_headers, est["id"], price="16.90")

    response = _availability(client, auth_headers, est["id"], target_type="product", target_id=fries["id"],
                             action="pause", channels=["RAPPI"], scope="item")

    assert response.status_code == 422


def test_kitchen_cannot_change_availability(client, auth_headers):
    est = _establishment(client, auth_headers)
    fries = _product(client, auth_headers, est["id"], price="16.90")
    login = client.post("/api/v1/auth/login", json={"email": "cozinha@comandahub.local", "password": "demo123"})
    kitchen = {"Authorization": f"Bearer {login.json()['access_token']}"}

    response = _availability(client, kitchen, est["id"], target_type="product", target_id=fries["id"],
                             action="pause", channels=["LOCAL"], scope="item")

    assert response.status_code == 403


# ------------------------------------------------------------------ ingredientes


def test_duplicate_ingredient_name_returns_conflict(client, auth_headers):
    est = _establishment(client, auth_headers)
    name = f"Picles {uuid4().hex[:6]}"
    _ingredient(client, auth_headers, est["id"], name)

    response = client.post(f"{API}/{est['id']}/ingredients", headers=auth_headers, json={"name": name})

    assert response.status_code == 409


def test_missing_main_ingredient_takes_item_off_that_channel(client, auth_headers):
    est = _establishment(client, auth_headers)
    potato = _ingredient(client, auth_headers, est["id"], f"Batata {uuid4().hex[:6]}")
    fries = _product(client, auth_headers, est["id"], price="16.90",
                     ingredients=[{"ingredient_id": potato["id"], "essential": True}])

    response = _availability(client, auth_headers, est["id"], target_type="ingredient", target_id=potato["id"],
                             action="pause", channels=["LOCAL"], scope="everywhere")

    assert response.status_code == 200, response.text
    assert _local_order(client, auth_headers, est["id"], fries["id"]).status_code == 422
    assert _external_order(est["id"], OrderSource.IFOOD, fries["id"]).items[0].product_id == fries["id"]


def test_missing_removable_ingredient_sells_item_without_it(client, auth_headers):
    est = _establishment(client, auth_headers)
    lettuce = _ingredient(client, auth_headers, est["id"], f"Alface {uuid4().hex[:6]}")
    groups = [{"name": "Adicionais", "min_choices": 0, "max_choices": 3,
               "options": [{"name": "Folha extra", "price_delta": "1.00", "ingredient_id": lettuce["id"]},
                           {"name": "Bacon extra", "price_delta": "5.00"}]}]
    burger = _product(client, auth_headers, est["id"], groups,
                      ingredients=[{"ingredient_id": lettuce["id"], "essential": False}])

    _availability(client, auth_headers, est["id"], target_type="ingredient", target_id=lettuce["id"],
                  action="pause", channels=["LOCAL"], scope="everywhere")

    response = _local_order(client, auth_headers, est["id"], burger["id"])
    assert response.status_code == 201, response.text
    missing = [o for o in response.json()["items"][0]["selected_options"] if o["group_name"] == "Em falta"]
    assert [o["name"] for o in missing] == [f"Sem {lettuce['name']}"]
    extra = _option(burger, "Adicionais", "Folha extra")["id"]
    assert _local_order(client, auth_headers, est["id"], burger["id"], [extra]).status_code == 422


def test_ingredient_paused_only_on_selected_items(client, auth_headers):
    est = _establishment(client, auth_headers)
    lettuce = _ingredient(client, auth_headers, est["id"], f"Alface {uuid4().hex[:6]}")
    link = [{"ingredient_id": lettuce["id"], "essential": False}]
    first = _product(client, auth_headers, est["id"], ingredients=link)
    second = _product(client, auth_headers, est["id"], ingredients=link)

    response = _availability(client, auth_headers, est["id"], target_type="ingredient", target_id=lettuce["id"],
                             action="pause", channels=["LOCAL"], scope="selected", product_ids=[first["id"]])

    assert response.status_code == 200, response.text
    first_item = _local_order(client, auth_headers, est["id"], first["id"]).json()["items"][0]
    second_item = _local_order(client, auth_headers, est["id"], second["id"]).json()["items"][0]
    assert any(o["group_name"] == "Em falta" for o in first_item["selected_options"])
    assert not any(o["group_name"] == "Em falta" for o in second_item["selected_options"])


def test_product_lists_its_ingredients_with_their_pauses(client, auth_headers):
    est = _establishment(client, auth_headers)
    lettuce = _ingredient(client, auth_headers, est["id"], f"Alface {uuid4().hex[:6]}")
    burger = _product(client, auth_headers, est["id"], ingredients=[{"ingredient_id": lettuce["id"], "essential": False}])
    _availability(client, auth_headers, est["id"], target_type="ingredient", target_id=lettuce["id"],
                  action="pause", channels=["IFOOD"], scope="everywhere")

    listed = _get_product(client, auth_headers, est["id"], burger["id"])["ingredients"]

    assert listed == [{"ingredient_id": lettuce["id"], "name": lettuce["name"], "essential": False,
                       "quantity": "0.000", "unit": "un", "paused_channels": ["IFOOD"]}]


def test_editing_product_keeps_ingredient_pause(client, auth_headers):
    est = _establishment(client, auth_headers)
    lettuce = _ingredient(client, auth_headers, est["id"], f"Alface {uuid4().hex[:6]}")
    link = [{"ingredient_id": lettuce["id"], "essential": False}]
    burger = _product(client, auth_headers, est["id"], ingredients=link)
    _availability(client, auth_headers, est["id"], target_type="ingredient", target_id=lettuce["id"],
                  action="pause", channels=["LOCAL"], scope="everywhere")

    client.patch(f"{API}/{est['id']}/products/{burger['id']}", headers=auth_headers,
                 json={"description": "Nova descricao", "ingredients": link})

    assert _get_product(client, auth_headers, est["id"], burger["id"])["ingredients"][0]["paused_channels"] == ["LOCAL"]


# ------------------------------------------------------------------ simulador


def _memory_product(paused_product=(), paused_option=()) -> Product:
    product = Product(id="p", name="Batata", price=Decimal("16.90"), is_available=True, paused_channels=list(paused_product))
    product.option_groups = [
        ProductOptionGroup(
            id="g", name="Molho", min_choices=1, max_choices=1, allow_repeat=False,
            options=[ProductOption(id="o", name="Barbecue", price_delta=Decimal("0"), is_available=True,
                                   paused_channels=list(paused_option))],
        )
    ]
    return product


def test_simulator_skips_item_paused_on_that_channel():
    product = _memory_product(paused_product=["IFOOD"])

    assert can_be_ordered(product, "IFOOD") is False
    assert can_be_ordered(product, "NINETY_NINE_FOOD") is True


def test_simulator_skips_item_whose_required_choice_is_paused_on_that_channel():
    product = _memory_product(paused_option=["IFOOD"])

    assert can_be_ordered(product, "IFOOD") is False
    assert pick_option_ids(product, random.Random(1), channel="NINETY_NINE_FOOD") == ["o"]
