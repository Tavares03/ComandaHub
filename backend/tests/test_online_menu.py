"""Cardapio online publico: o cliente ve o cardapio pelo link da loja, faz o pedido e acompanha."""
from __future__ import annotations

import random
from decimal import Decimal
from uuid import uuid4

from tests.helpers import API, establishment, get_product, product

PUBLIC = "/api/v1/public"
STORE = "Burger Station"


def _enable(client, headers, est_id, slug=None, enabled=True):
    slug = slug or f"loja-{uuid4().hex[:6]}"
    response = client.patch(f"{API}/{est_id}", headers=headers,
                            json={"slug": slug, "online_menu_enabled": enabled, "whatsapp": "11988887777"})
    assert response.status_code == 200, response.text
    return slug


def _zone(client, headers, est_id, fee="6.00"):
    return client.post(f"{API}/{est_id}/delivery-zones", headers=headers,
                       json={"name": f"Bairro {uuid4().hex[:6]}", "fee": fee}).json()


def _phone():
    return f"1198{random.randint(1000000, 9999999)}"


def _checkout(client, slug, product_id, **extra):
    body = {
        "customer_name": "Ana Online",
        "customer_phone": _phone(),
        "fulfillment_type": "PICKUP",
        "payment_method": "PIX",
        "items": [{"product_id": product_id, "quantity": 2}],
        **extra,
    }
    return client.post(f"{PUBLIC}/stores/{slug}/orders", json=body)


def test_public_menu_lists_items_sold_locally_without_internal_cost(client, auth_headers):
    est = establishment(client, auth_headers, STORE)
    slug = _enable(client, auth_headers, est["id"])
    visible = product(client, auth_headers, est["id"], price="30.00", channel_prices={"LOCAL": "28.00"})
    paused = product(client, auth_headers, est["id"])
    client.post(f"{API}/{est['id']}/availability", headers=auth_headers, json={
        "target_type": "product", "target_id": paused["id"], "action": "pause", "channels": ["LOCAL"], "scope": "item"})

    menu = client.get(f"{PUBLIC}/stores/{slug}").json()

    by_id = {item["id"]: item for item in menu["products"]}
    assert menu["name"] == STORE
    assert visible["id"] in by_id and paused["id"] not in by_id
    assert Decimal(by_id[visible["id"]]["price"]) == Decimal("28.00")
    assert "unit_cost" not in by_id[visible["id"]]
    assert menu["categories"]


def test_disabled_menu_is_not_found(client, auth_headers):
    est = establishment(client, auth_headers, "Pizzaria Bella Massa")
    slug = _enable(client, auth_headers, est["id"], enabled=False)

    assert client.get(f"{PUBLIC}/stores/{slug}").status_code == 404


def test_online_delivery_order_goes_to_the_board_with_neighborhood_fee(client, auth_headers):
    est = establishment(client, auth_headers, STORE)
    slug = _enable(client, auth_headers, est["id"])
    item = product(client, auth_headers, est["id"], price="25.00")
    zone = _zone(client, auth_headers, est["id"], fee="6.00")

    response = _checkout(client, slug, item["id"], fulfillment_type="DELIVERY", delivery_address="Rua X, 10",
                         delivery_zone_id=zone["id"], payment_method="CASH", change_for="100")

    assert response.status_code == 201, response.text
    created = response.json()
    assert Decimal(created["total"]) == Decimal("56.00")
    board = client.get(f"{API}/{est['id']}/orders/board", headers=auth_headers).json()["items"]
    order = next(o for o in board if o["order_number"] == created["order_number"])
    assert order["source"] == "OWN_DELIVERY"
    assert order["status"] == "NEW"
    assert order["payment_status"] == "PENDING"
    assert order["neighborhood"] == zone["name"]
    assert "Troco para R$ 100.00" in order["notes"]


def test_online_pickup_order_and_tracking_by_token(client, auth_headers):
    est = establishment(client, auth_headers, STORE)
    slug = _enable(client, auth_headers, est["id"])
    item = product(client, auth_headers, est["id"], price="20.00")

    created = _checkout(client, slug, item["id"]).json()
    tracking = client.get(f"{PUBLIC}/orders/{created['public_token']}").json()

    assert tracking["order_number"] == created["order_number"]
    assert tracking["status"] == "NEW"
    assert tracking["fulfillment_type"] == "PICKUP"
    assert Decimal(tracking["total"]) == Decimal("40.00")
    assert tracking["store_name"] == STORE
    assert client.get(f"{PUBLIC}/orders/nao-existe").status_code == 404


def test_delivery_needs_neighborhood_when_store_has_neighborhoods(client, auth_headers):
    est = establishment(client, auth_headers, STORE)
    slug = _enable(client, auth_headers, est["id"])
    item = product(client, auth_headers, est["id"])
    _zone(client, auth_headers, est["id"])

    response = _checkout(client, slug, item["id"], fulfillment_type="DELIVERY", delivery_address="Rua X, 10")

    assert response.status_code == 422


def test_online_order_needs_phone(client, auth_headers):
    est = establishment(client, auth_headers, STORE)
    slug = _enable(client, auth_headers, est["id"])
    item = product(client, auth_headers, est["id"])

    response = _checkout(client, slug, item["id"], customer_phone="123")

    assert response.status_code == 422


def test_online_order_cannot_buy_item_paused_on_local(client, auth_headers):
    est = establishment(client, auth_headers, STORE)
    slug = _enable(client, auth_headers, est["id"])
    item = product(client, auth_headers, est["id"])
    client.post(f"{API}/{est['id']}/availability", headers=auth_headers, json={
        "target_type": "product", "target_id": item["id"], "action": "pause", "channels": ["LOCAL"], "scope": "item"})

    assert _checkout(client, slug, item["id"]).status_code == 422
    assert get_product(client, auth_headers, est["id"], item["id"])["paused_channels"] == ["LOCAL"]


def test_closed_store_shows_menu_but_refuses_orders(client, auth_headers):
    est = establishment(client, auth_headers, STORE)
    slug = _enable(client, auth_headers, est["id"])
    item = product(client, auth_headers, est["id"])
    client.patch(f"{API}/{est['id']}", headers=auth_headers, json={"online_orders_open": False})

    try:
        menu = client.get(f"{PUBLIC}/stores/{slug}")
        refused = _checkout(client, slug, item["id"])
    finally:
        client.patch(f"{API}/{est['id']}", headers=auth_headers, json={"online_orders_open": True})

    assert menu.status_code == 200
    assert menu.json()["accepting_orders"] is False
    assert refused.status_code == 409
    assert _checkout(client, slug, item["id"]).status_code == 201


def test_online_order_cannot_redeem_loyalty_reward(client, auth_headers):
    est = establishment(client, auth_headers, STORE)
    slug = _enable(client, auth_headers, est["id"])
    item = product(client, auth_headers, est["id"], price="20.00")

    response = _checkout(client, slug, item["id"], use_loyalty_reward=True)

    assert response.status_code == 201, response.text
    assert Decimal(response.json()["total"]) == Decimal("40.00")


def test_online_order_does_not_overwrite_known_customer(client, auth_headers):
    est = establishment(client, auth_headers, STORE)
    slug = _enable(client, auth_headers, est["id"])
    item = product(client, auth_headers, est["id"])
    phone = _phone()
    client.post(f"{API}/{est['id']}/orders", headers=auth_headers, json={
        "fulfillment_type": "DELIVERY", "payment_method": "PIX", "customer_name": "Maria Original", "customer_phone": phone,
        "delivery_address": "Rua Verdadeira, 1", "items": [{"product_id": item["id"], "quantity": 1}]})

    _checkout(client, slug, item["id"], customer_name="Impostor", customer_phone=phone,
              fulfillment_type="DELIVERY", delivery_address="Rua Falsa, 2",
              delivery_zone_id=_zone(client, auth_headers, est["id"])["id"])

    customer = client.get(f"{API}/{est['id']}/customers/lookup", headers=auth_headers, params={"phone": phone}).json()
    assert customer["name"] == "Maria Original"
    assert customer["address"] == "Rua Verdadeira, 1"


def test_too_many_online_orders_from_same_device_are_blocked(client, auth_headers):
    est = establishment(client, auth_headers, STORE)
    slug = _enable(client, auth_headers, est["id"])
    item = product(client, auth_headers, est["id"])

    codes = [_checkout(client, slug, item["id"]).status_code for _ in range(11)]

    assert codes[:10] == [201] * 10
    assert codes[10] == 429
