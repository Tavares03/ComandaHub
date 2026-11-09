from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo


def _first_establishment(client, headers):
    return client.get("/api/v1/establishments", headers=headers).json()[0]


def _products(client, headers, establishment_id):
    return client.get(f"/api/v1/establishments/{establishment_id}/products", headers=headers).json()


def _login(client, email):
    response = client.post("/api/v1/auth/login", json={"email": email, "password": "demo123"})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_login_accepts_demo_local_domain_and_is_case_insensitive(client):
    response = client.post("/api/v1/auth/login", json={"email": "  Admin@ComandaHub.local ", "password": "demo123"})
    assert response.status_code == 200, response.text
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {response.json()['access_token']}"})
    assert me.status_code == 200
    assert me.json()["email"] == "admin@comandahub.local"


def test_wrong_password_is_rejected(client):
    response = client.post("/api/v1/auth/login", json={"email": "admin@comandahub.local", "password": "errada"})
    assert response.status_code == 401


def test_option_from_another_product_is_rejected(client, auth_headers):
    establishment = _first_establishment(client, auth_headers)
    products = _products(client, auth_headers, establishment["id"])
    with_options = [p for p in products if p["option_groups"] and p["is_available"]]
    without_options = [p for p in products if not p["option_groups"] and p["is_available"]]
    foreign_option = with_options[0]["option_groups"][0]["options"][0]["id"]
    payload = {
        "fulfillment_type": "COUNTER",
        "payment_method": "CASH",
        "items": [{"product_id": without_options[0]["id"], "quantity": 1, "option_ids": [foreign_option]}],
    }
    response = client.post(f"/api/v1/establishments/{establishment['id']}/orders", headers=auth_headers, json=payload)
    assert response.status_code == 422


def test_option_max_choices_is_enforced(client, auth_headers):
    establishment = _first_establishment(client, auth_headers)
    products = _products(client, auth_headers, establishment["id"])
    product = next(p for p in products if p["option_groups"] and p["is_available"])
    group = product["option_groups"][0]
    option_ids = [option["id"] for option in group["options"]]
    too_many = (option_ids * (group["max_choices"] + 1))[: group["max_choices"] + 1]
    payload = {
        "fulfillment_type": "COUNTER",
        "payment_method": "CASH",
        "items": [{"product_id": product["id"], "quantity": 1, "option_ids": too_many}],
    }
    response = client.post(f"/api/v1/establishments/{establishment['id']}/orders", headers=auth_headers, json=payload)
    assert response.status_code == 422


def test_discount_cannot_exceed_subtotal(client, auth_headers):
    establishment = _first_establishment(client, auth_headers)
    product = next(p for p in _products(client, auth_headers, establishment["id"]) if p["is_available"])
    payload = {
        "fulfillment_type": "COUNTER",
        "payment_method": "CASH",
        "discount": "9999.00",
        "items": [{"product_id": product["id"], "quantity": 1}],
    }
    response = client.post(f"/api/v1/establishments/{establishment['id']}/orders", headers=auth_headers, json=payload)
    assert response.status_code == 422


def test_negative_delivery_fee_is_rejected(client, auth_headers):
    establishment = _first_establishment(client, auth_headers)
    product = next(p for p in _products(client, auth_headers, establishment["id"]) if p["is_available"])
    payload = {
        "fulfillment_type": "DELIVERY",
        "delivery_address": "Rua A, 1",
        "payment_method": "PIX",
        "delivery_fee": "-5.00",
        "items": [{"product_id": product["id"], "quantity": 1}],
    }
    response = client.post(f"/api/v1/establishments/{establishment['id']}/orders", headers=auth_headers, json=payload)
    assert response.status_code == 422


def test_local_day_bounds_use_establishment_timezone():
    from app.core.timeutils import local_day_bounds

    tz = ZoneInfo("America/Sao_Paulo")
    late_night = datetime(2026, 11, 7, 22, 30, tzinfo=tz).astimezone(timezone.utc)
    start, end = local_day_bounds("America/Sao_Paulo", late_night)
    assert start == datetime(2026, 11, 7, 0, 0, tzinfo=tz)
    assert end == datetime(2026, 11, 8, 0, 0, tzinfo=tz)


def test_board_returns_every_active_order(client, auth_headers):
    establishment = _first_establishment(client, auth_headers)
    url = f"/api/v1/establishments/{establishment['id']}"
    client.post(f"/api/v1/dev{url[7:]}/simulate-order", headers=auth_headers, json={"source": "IFOOD", "quantity": 3})
    everything = client.get(f"{url}/orders", headers=auth_headers, params={"limit": 200}).json()["items"]
    active_ids = {o["id"] for o in everything if o["status"] not in {"FINISHED", "CANCELED"}}
    board = client.get(f"{url}/orders/board", headers=auth_headers)
    assert board.status_code == 200
    board_ids = {o["id"] for o in board.json()["items"]}
    assert active_ids <= board_ids


def test_duplicate_product_name_returns_conflict(client, auth_headers):
    establishment = _first_establishment(client, auth_headers)
    product = _products(client, auth_headers, establishment["id"])[0]
    payload = {"category_id": product["category_id"], "name": product["name"], "price": "10.00"}
    response = client.post(f"/api/v1/establishments/{establishment['id']}/products", headers=auth_headers, json=payload)
    assert response.status_code == 409


def test_kitchen_cannot_cancel_orders(client, auth_headers):
    establishment = _first_establishment(client, auth_headers)
    order = client.post(
        f"/api/v1/dev/establishments/{establishment['id']}/simulate-order",
        headers=auth_headers,
        json={"source": "IFOOD", "quantity": 1},
    ).json()[0]
    kitchen = _login(client, "cozinha@comandahub.local")
    response = client.patch(
        f"/api/v1/establishments/{establishment['id']}/orders/{order['id']}/status",
        headers=kitchen,
        json={"status": "CANCELED", "cancel_reason": "teste"},
    )
    assert response.status_code == 403


def test_order_numbers_are_unique(client, auth_headers):
    establishment = _first_establishment(client, auth_headers)
    client.post(
        f"/api/v1/dev/establishments/{establishment['id']}/simulate-order",
        headers=auth_headers,
        json={"source": "COUNTER", "quantity": 5},
    )
    orders = client.get(f"/api/v1/establishments/{establishment['id']}/orders", headers=auth_headers, params={"limit": 200}).json()["items"]
    numbers = [o["order_number"] for o in orders]
    assert len(numbers) == len(set(numbers))
