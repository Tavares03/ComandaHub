"""Estoque por ingrediente: ficha tecnica, baixa nos pedidos, custo e pausa automatica."""
from __future__ import annotations

from decimal import Decimal

from app.models.order import OrderSource
from tests.helpers import (
    API,
    cancel,
    establishment,
    external_order,
    get_ingredient,
    get_product,
    ingredient,
    local_order,
    option,
    product,
)


def _stock(client, headers, est_id, ingredient_id, **body):
    return client.post(f"{API}/{est_id}/ingredients/{ingredient_id}/stock", headers=headers, json=body)


def _qty(client, headers, est_id, ingredient_id) -> Decimal:
    return Decimal(str(get_ingredient(client, headers, est_id, ingredient_id)["stock_quantity"]))


def test_order_takes_recipe_out_of_stock(client, auth_headers):
    est = establishment(client, auth_headers)
    potato = ingredient(client, auth_headers, est["id"], unit="kg", stock_quantity="10")
    fries = product(client, auth_headers, est["id"], ingredients=[{"ingredient_id": potato["id"], "essential": True, "quantity": "0.2"}])

    response = local_order(client, auth_headers, est["id"], fries["id"], quantity=2)

    assert response.status_code == 201, response.text
    assert _qty(client, auth_headers, est["id"], potato["id"]) == Decimal("9.6")


def test_untracked_ingredient_stock_stays_empty(client, auth_headers):
    est = establishment(client, auth_headers)
    lettuce = ingredient(client, auth_headers, est["id"], unit="un")
    burger = product(client, auth_headers, est["id"], ingredients=[{"ingredient_id": lettuce["id"], "quantity": "1"}])

    local_order(client, auth_headers, est["id"], burger["id"])

    assert get_ingredient(client, auth_headers, est["id"], lettuce["id"])["stock_quantity"] is None


def test_combo_side_takes_the_linked_product_recipe(client, auth_headers):
    est = establishment(client, auth_headers)
    potato = ingredient(client, auth_headers, est["id"], unit="kg", stock_quantity="5")
    fries = product(client, auth_headers, est["id"], ingredients=[{"ingredient_id": potato["id"], "essential": True, "quantity": "0.15"}])
    burger = product(client, auth_headers, est["id"], groups=[
        {"name": "Combo", "min_choices": 0, "max_choices": 1, "options": [{"name": "Fazer combo", "price_delta": "18"}]},
        {"name": "Acompanhamento", "min_choices": 1, "max_choices": 1, "depends_on": {"group": 0, "option": 0},
         "options": [{"name": "Fritas", "price_delta": "0", "linked_product_id": fries["id"]}]},
    ])
    picks = [option(burger, "Combo", "Fazer combo")["id"], option(burger, "Acompanhamento", "Fritas")["id"]]

    response = local_order(client, auth_headers, est["id"], burger["id"], picks)

    assert response.status_code == 201, response.text
    assert _qty(client, auth_headers, est["id"], potato["id"]) == Decimal("4.85")


def test_extra_option_takes_its_own_quantity(client, auth_headers):
    est = establishment(client, auth_headers)
    bacon = ingredient(client, auth_headers, est["id"], unit="kg", stock_quantity="2")
    burger = product(client, auth_headers, est["id"], groups=[
        {"name": "Adicionais", "min_choices": 0, "max_choices": 5, "allow_repeat": True,
         "options": [{"name": "Bacon extra", "price_delta": "5", "ingredient_id": bacon["id"], "ingredient_quantity": "0.03"}]},
    ])
    extra = option(burger, "Adicionais", "Bacon extra")["id"]

    response = client.post(f"{API}/{est['id']}/orders", headers=auth_headers, json={
        "fulfillment_type": "COUNTER", "payment_method": "CASH",
        "items": [{"product_id": burger["id"], "quantity": 1, "options": [{"option_id": extra, "quantity": 2}]}],
    })

    assert response.status_code == 201, response.text
    assert _qty(client, auth_headers, est["id"], bacon["id"]) == Decimal("1.94")


def test_removed_ingredient_is_not_taken_from_stock(client, auth_headers):
    est = establishment(client, auth_headers)
    lettuce = ingredient(client, auth_headers, est["id"], unit="un", stock_quantity="10")
    burger = product(
        client, auth_headers, est["id"],
        groups=[{"name": "Retirar", "min_choices": 0, "max_choices": 0,
                 "options": [{"name": "Sem alface", "price_delta": "0", "ingredient_id": lettuce["id"]}]}],
        ingredients=[{"ingredient_id": lettuce["id"], "quantity": "1"}],
    )

    local_order(client, auth_headers, est["id"], burger["id"], [option(burger, "Retirar", "Sem alface")["id"]])

    assert _qty(client, auth_headers, est["id"], lettuce["id"]) == Decimal("10")


def test_canceling_order_gives_stock_back(client, auth_headers):
    est = establishment(client, auth_headers)
    potato = ingredient(client, auth_headers, est["id"], unit="kg", stock_quantity="3")
    fries = product(client, auth_headers, est["id"], ingredients=[{"ingredient_id": potato["id"], "essential": True, "quantity": "0.5"}])
    order = local_order(client, auth_headers, est["id"], fries["id"]).json()

    response = cancel(client, auth_headers, est["id"], order["id"])

    assert response.status_code == 200, response.text
    assert _qty(client, auth_headers, est["id"], potato["id"]) == Decimal("3")


def test_stock_running_out_pauses_ingredient_on_every_channel(client, auth_headers):
    est = establishment(client, auth_headers)
    potato = ingredient(client, auth_headers, est["id"], unit="kg", stock_quantity="0.3")
    fries = product(client, auth_headers, est["id"], ingredients=[{"ingredient_id": potato["id"], "essential": True, "quantity": "0.3"}])

    assert local_order(client, auth_headers, est["id"], fries["id"]).status_code == 201

    assert get_ingredient(client, auth_headers, est["id"], potato["id"])["auto_paused"] is True
    assert get_product(client, auth_headers, est["id"], fries["id"])["ingredients"][0]["paused_channels"] == ["IFOOD", "NINETY_NINE_FOOD", "LOCAL"]
    assert local_order(client, auth_headers, est["id"], fries["id"]).status_code == 422


def test_purchase_brings_auto_paused_ingredient_back(client, auth_headers):
    est = establishment(client, auth_headers)
    potato = ingredient(client, auth_headers, est["id"], unit="kg", stock_quantity="0.3")
    fries = product(client, auth_headers, est["id"], ingredients=[{"ingredient_id": potato["id"], "essential": True, "quantity": "0.3"}])
    local_order(client, auth_headers, est["id"], fries["id"])

    response = _stock(client, auth_headers, est["id"], potato["id"], kind="PURCHASE", quantity="5", unit_cost="7.50")

    assert response.status_code == 200, response.text
    assert response.json()["stock_quantity"] == "5.000"
    assert response.json()["cost_per_unit"] == "7.5000"
    assert response.json()["auto_paused"] is False
    assert local_order(client, auth_headers, est["id"], fries["id"]).status_code == 201


def test_restock_keeps_pause_that_was_made_by_hand(client, auth_headers):
    est = establishment(client, auth_headers)
    potato = ingredient(client, auth_headers, est["id"], unit="kg", stock_quantity="0.3")
    fries = product(client, auth_headers, est["id"], ingredients=[{"ingredient_id": potato["id"], "essential": True, "quantity": "0.3"}])
    client.post(f"{API}/{est['id']}/availability", headers=auth_headers, json={
        "target_type": "ingredient", "target_id": potato["id"], "action": "pause", "channels": ["NINETY_NINE_FOOD"], "scope": "everywhere"})
    local_order(client, auth_headers, est["id"], fries["id"])

    _stock(client, auth_headers, est["id"], potato["id"], kind="PURCHASE", quantity="5")

    assert get_product(client, auth_headers, est["id"], fries["id"])["ingredients"][0]["paused_channels"] == ["NINETY_NINE_FOOD"]


def test_count_sets_stock_and_is_kept_in_history(client, auth_headers):
    est = establishment(client, auth_headers)
    cheese = ingredient(client, auth_headers, est["id"], unit="kg", stock_quantity="4")

    response = _stock(client, auth_headers, est["id"], cheese["id"], kind="ADJUST", quantity="3.5", note="Contagem de sexta")

    assert response.status_code == 200, response.text
    assert Decimal(response.json()["stock_quantity"]) == Decimal("3.5")
    history = client.get(f"{API}/{est['id']}/ingredients/{cheese['id']}/movements", headers=auth_headers).json()
    assert [(Decimal(m["delta"]), m["reason"]) for m in history][:1] == [(Decimal("-0.5"), "ADJUST")]


def test_item_cost_comes_from_recipe_and_is_saved_in_the_order(client, auth_headers):
    est = establishment(client, auth_headers)
    potato = ingredient(client, auth_headers, est["id"], unit="kg", cost_per_unit="8.00")
    oil = ingredient(client, auth_headers, est["id"], unit="L", cost_per_unit="10.00")
    fries = product(client, auth_headers, est["id"], ingredients=[
        {"ingredient_id": potato["id"], "essential": True, "quantity": "0.15"},
        {"ingredient_id": oil["id"], "quantity": "0.02"},
    ])

    assert Decimal(get_product(client, auth_headers, est["id"], fries["id"])["unit_cost"]) == Decimal("1.40")
    order = local_order(client, auth_headers, est["id"], fries["id"]).json()
    assert Decimal(order["items"][0]["unit_cost"]) == Decimal("1.40")


def test_ingredient_out_everywhere_also_leaves_combos_of_items_that_need_it(client, auth_headers):
    est = establishment(client, auth_headers)
    potato = ingredient(client, auth_headers, est["id"])
    fries = product(client, auth_headers, est["id"], ingredients=[{"ingredient_id": potato["id"], "essential": True}])
    burger = product(client, auth_headers, est["id"], groups=[
        {"name": "Acompanhamento", "min_choices": 0, "max_choices": 1,
         "options": [{"name": "Fritas", "price_delta": "0", "linked_product_id": fries["id"]}]},
    ])

    client.post(f"{API}/{est['id']}/availability", headers=auth_headers, json={
        "target_type": "ingredient", "target_id": potato["id"], "action": "pause", "channels": ["LOCAL"], "scope": "everywhere"})

    burger = get_product(client, auth_headers, est["id"], burger["id"])
    assert option(burger, "Acompanhamento", "Fritas")["paused_channels"] == ["LOCAL"]


def test_ifood_order_also_takes_stock(client, auth_headers):
    est = establishment(client, auth_headers)
    potato = ingredient(client, auth_headers, est["id"], unit="kg", stock_quantity="1")
    fries = product(client, auth_headers, est["id"], ingredients=[{"ingredient_id": potato["id"], "essential": True, "quantity": "0.25"}])

    external_order(est["id"], OrderSource.IFOOD, fries["id"])

    assert _qty(client, auth_headers, est["id"], potato["id"]) == Decimal("0.75")
