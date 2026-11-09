"""Personalizacao de itens: grupos de opcoes (ponto, adicionais, retirar, combo, pizza meio a meio)."""
from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

API = "/api/v1/establishments"


def _establishment(client, headers, name="Burger Station"):
    return next(e for e in client.get(API, headers=headers).json() if e["name"] == name)


def _create_product(client, headers, establishment_id, groups, price="40.00"):
    category_id = client.get(f"{API}/{establishment_id}/categories", headers=headers).json()[0]["id"]
    payload = {"category_id": category_id, "name": f"Teste {uuid4().hex[:8]}", "price": price, "option_groups": groups}
    return client.post(f"{API}/{establishment_id}/products", headers=headers, json=payload)


def _product(client, headers, establishment_id, groups, price="40.00"):
    response = _create_product(client, headers, establishment_id, groups, price)
    assert response.status_code == 201, response.text
    return response.json()


def _option_id(product, group_name, option_name):
    group = next(g for g in product["option_groups"] if g["name"] == group_name)
    return next(o["id"] for o in group["options"] if o["name"] == option_name)


def _order_item(client, headers, establishment_id, item):
    payload = {"fulfillment_type": "COUNTER", "payment_method": "CASH", "items": [item]}
    return client.post(f"{API}/{establishment_id}/orders", headers=headers, json=payload)


PIZZA_FLAVORS = [
    {"name": "Calabresa", "price_delta": "0.00"},
    {"name": "Mussarela", "price_delta": "0.00"},
    {"name": "Portuguesa", "price_delta": "6.00"},
    {"name": "Camarao", "price_delta": "20.00"},
]


def test_repeatable_addon_is_charged_per_unit(client, auth_headers):
    est = _establishment(client, auth_headers)
    product = _product(
        client,
        auth_headers,
        est["id"],
        [{"name": "Adicionais", "min_choices": 0, "max_choices": 5, "allow_repeat": True,
          "options": [{"name": "Carne extra", "price_delta": "9.00"}]}],
    )
    carne = _option_id(product, "Adicionais", "Carne extra")

    response = _order_item(client, auth_headers, est["id"],
                           {"product_id": product["id"], "quantity": 1, "options": [{"option_id": carne, "quantity": 2}]})

    assert response.status_code == 201, response.text
    assert Decimal(response.json()["items"][0]["unit_price"]) == Decimal("58.00")


def test_repeating_option_is_rejected_when_group_does_not_allow_it(client, auth_headers):
    est = _establishment(client, auth_headers)
    product = _product(
        client,
        auth_headers,
        est["id"],
        [{"name": "Bebida", "min_choices": 0, "max_choices": 2,
          "options": [{"name": "Coca-Cola", "price_delta": "0.00"}, {"name": "Guarana", "price_delta": "0.00"}]}],
    )
    coca = _option_id(product, "Bebida", "Coca-Cola")

    response = _order_item(client, auth_headers, est["id"],
                           {"product_id": product["id"], "quantity": 1, "options": [{"option_id": coca, "quantity": 2}]})

    assert response.status_code == 422


def test_half_and_half_with_max_pricing_charges_most_expensive_flavor(client, auth_headers):
    est = _establishment(client, auth_headers)
    product = _product(
        client,
        auth_headers,
        est["id"],
        [{"name": "Sabores", "min_choices": 1, "max_choices": 2, "pricing_mode": "MAX", "options": PIZZA_FLAVORS}],
        price="50.00",
    )
    item = {
        "product_id": product["id"],
        "quantity": 1,
        "options": [
            {"option_id": _option_id(product, "Sabores", "Portuguesa")},
            {"option_id": _option_id(product, "Sabores", "Camarao")},
        ],
    }

    response = _order_item(client, auth_headers, est["id"], item)

    assert response.status_code == 201, response.text
    assert Decimal(response.json()["items"][0]["unit_price"]) == Decimal("70.00")


def test_half_and_half_with_average_pricing_charges_mean_of_flavors(client, auth_headers):
    est = _establishment(client, auth_headers)
    product = _product(
        client,
        auth_headers,
        est["id"],
        [{"name": "Sabores", "min_choices": 1, "max_choices": 2, "pricing_mode": "AVERAGE", "options": PIZZA_FLAVORS}],
        price="50.00",
    )
    item = {
        "product_id": product["id"],
        "quantity": 1,
        "options": [
            {"option_id": _option_id(product, "Sabores", "Portuguesa")},
            {"option_id": _option_id(product, "Sabores", "Camarao")},
        ],
    }

    response = _order_item(client, auth_headers, est["id"], item)

    assert response.status_code == 201, response.text
    assert Decimal(response.json()["items"][0]["unit_price"]) == Decimal("63.00")


def test_order_snapshot_keeps_group_quantity_and_note_of_each_choice(client, auth_headers):
    est = _establishment(client, auth_headers)
    product = _product(
        client,
        auth_headers,
        est["id"],
        [
            {"name": "Sabores", "min_choices": 1, "max_choices": 2, "pricing_mode": "MAX", "options": PIZZA_FLAVORS},
            {"name": "Borda", "min_choices": 1, "max_choices": 1,
             "options": [{"name": "Sem recheio", "price_delta": "0.00"}, {"name": "Catupiry", "price_delta": "10.00"}]},
        ],
        price="50.00",
    )
    item = {
        "product_id": product["id"],
        "quantity": 1,
        "notes": "Cortar em 12",
        "options": [
            {"option_id": _option_id(product, "Sabores", "Calabresa"), "notes": "sem cebola"},
            {"option_id": _option_id(product, "Sabores", "Mussarela")},
            {"option_id": _option_id(product, "Borda", "Catupiry")},
        ],
    }

    response = _order_item(client, auth_headers, est["id"], item)

    assert response.status_code == 201, response.text
    saved = response.json()["items"][0]
    assert saved["notes"] == "Cortar em 12"
    assert Decimal(saved["unit_price"]) == Decimal("60.00")
    simplified = [(s["group_name"], s["name"], s["quantity"], s.get("notes")) for s in saved["selected_options"]]
    assert simplified == [
        ("Sabores", "Calabresa", 1, "sem cebola"),
        ("Sabores", "Mussarela", 1, None),
        ("Borda", "Catupiry", 1, None),
    ]


def test_missing_required_choice_is_rejected(client, auth_headers):
    est = _establishment(client, auth_headers)
    product = _product(
        client,
        auth_headers,
        est["id"],
        [
            {"name": "Ponto da carne", "min_choices": 1, "max_choices": 1,
             "options": [{"name": "Ao ponto"}, {"name": "Bem passado"}]},
            {"name": "Retirar", "min_choices": 0, "max_choices": 0, "options": [{"name": "Sem alface"}]},
        ],
    )

    response = _order_item(client, auth_headers, est["id"], {
        "product_id": product["id"],
        "quantity": 1,
        "options": [{"option_id": _option_id(product, "Retirar", "Sem alface")}],
    })

    assert response.status_code == 422


def test_unlimited_group_accepts_many_choices(client, auth_headers):
    est = _establishment(client, auth_headers)
    removals = [{"name": f"Sem item {n}"} for n in range(6)]
    product = _product(client, auth_headers, est["id"],
                       [{"name": "Retirar", "min_choices": 0, "max_choices": 0, "options": removals}])
    options = [{"option_id": o["id"]} for o in product["option_groups"][0]["options"]]

    response = _order_item(client, auth_headers, est["id"], {"product_id": product["id"], "quantity": 1, "options": options})

    assert response.status_code == 201, response.text


def test_legacy_option_ids_are_still_priced(client, auth_headers):
    est = _establishment(client, auth_headers)
    product = _product(client, auth_headers, est["id"],
                       [{"name": "Adicionais", "min_choices": 0, "max_choices": 3,
                         "options": [{"name": "Bacon extra", "price_delta": "5.00"}]}])

    response = _order_item(client, auth_headers, est["id"], {
        "product_id": product["id"], "quantity": 2, "option_ids": [_option_id(product, "Adicionais", "Bacon extra")]
    })

    assert response.status_code == 201, response.text
    assert Decimal(response.json()["items"][0]["total"]) == Decimal("90.00")


def test_product_keeps_group_settings_and_order(client, auth_headers):
    est = _establishment(client, auth_headers)
    groups = [
        {"name": "Tamanho", "min_choices": 1, "max_choices": 1,
         "options": [{"name": "P"}, {"name": "M", "price_delta": "4.00"}, {"name": "G", "price_delta": "8.00"}]},
        {"name": "Sabores", "min_choices": 1, "max_choices": 2, "pricing_mode": "AVERAGE", "options": PIZZA_FLAVORS},
        {"name": "Adicionais", "min_choices": 0, "max_choices": 4, "allow_repeat": True,
         "options": [{"name": "Bacon", "price_delta": "5.00"}]},
        {"name": "Retirar", "min_choices": 0, "max_choices": 0, "options": [{"name": "Sem cebola"}, {"name": "Sem azeitona"}]},
    ]
    product = _product(client, auth_headers, est["id"], groups)

    listed = next(p for p in client.get(f"{API}/{est['id']}/products", headers=auth_headers).json() if p["id"] == product["id"])

    assert [g["name"] for g in listed["option_groups"]] == ["Tamanho", "Sabores", "Adicionais", "Retirar"]
    assert [o["name"] for o in listed["option_groups"][1]["options"]] == ["Calabresa", "Mussarela", "Portuguesa", "Camarao"]
    assert [(g["pricing_mode"], g["allow_repeat"]) for g in listed["option_groups"]] == [
        ("SUM", False), ("AVERAGE", False), ("SUM", True), ("SUM", False)
    ]


def test_group_with_min_above_max_is_rejected(client, auth_headers):
    est = _establishment(client, auth_headers)
    response = _create_product(client, auth_headers, est["id"],
                               [{"name": "Sabores", "min_choices": 2, "max_choices": 1, "options": PIZZA_FLAVORS}])
    assert response.status_code == 422


def test_required_group_without_enough_options_is_rejected(client, auth_headers):
    est = _establishment(client, auth_headers)
    response = _create_product(client, auth_headers, est["id"],
                               [{"name": "Bebida", "min_choices": 2, "max_choices": 2, "options": [{"name": "Coca-Cola"}]}])
    assert response.status_code == 422


def test_simulated_orders_fill_required_choices(client, auth_headers):
    pizzaria = _establishment(client, auth_headers, "Pizzaria Bella Massa")

    response = client.post(f"/api/v1/dev/establishments/{pizzaria['id']}/simulate-order",
                           headers=auth_headers, json={"source": "IFOOD", "quantity": 10})

    assert response.status_code == 201, response.text
