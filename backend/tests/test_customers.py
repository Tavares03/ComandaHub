"""Clientes (cadastro pelo telefone), programa de fidelidade e cupons de desconto."""
from __future__ import annotations

import random
from decimal import Decimal

from datetime import datetime
from zoneinfo import ZoneInfo

from tests.helpers import API, cancel, establishment, finish, product

STORE = "Pizzaria Bella Massa"


def _phone() -> str:
    return f"1199{random.randint(1000000, 9999999)}"


def _order(client, headers, est_id, product_id, phone=None, name="Cliente Teste", **extra):
    payload = {
        "fulfillment_type": "DELIVERY",
        "payment_method": "PIX",
        "customer_name": name,
        "customer_phone": phone,
        "delivery_address": "Rua das Flores, 10",
        "items": [{"product_id": product_id, "quantity": 1}],
        **extra,
    }
    return client.post(f"{API}/{est_id}/orders", headers=headers, json=payload)


def _coupon(client, headers, est_id, **body):
    response = client.post(f"{API}/{est_id}/coupons", headers=headers, json=body)
    assert response.status_code == 201, response.text
    return response.json()


def _loyalty(client, headers, est_id, enabled=True, goal=2, reward="10.00"):
    response = client.patch(f"{API}/{est_id}", headers=headers,
                            json={"loyalty_enabled": enabled, "loyalty_goal": goal, "loyalty_reward": reward})
    assert response.status_code == 200, response.text


# ------------------------------------------------------------------ clientes


def test_order_with_phone_saves_customer_and_reuses_it(client, auth_headers):
    est = establishment(client, auth_headers, STORE)
    item = product(client, auth_headers, est["id"], price="40.00")
    phone = _phone()

    _order(client, auth_headers, est["id"], item["id"], phone=phone, name="Maria")
    formatted = f"({phone[:2]}) {phone[2:7]}-{phone[7:]}"
    second = _order(client, auth_headers, est["id"], item["id"], phone=formatted, name="Maria Souza")

    assert second.status_code == 201, second.text
    found = client.get(f"{API}/{est['id']}/customers/lookup", headers=auth_headers, params={"phone": phone}).json()
    assert found["name"] == "Maria Souza"
    assert found["phone"] == phone
    assert found["address"] == "Rua das Flores, 10"
    assert found["order_count"] == 2
    assert Decimal(found["total_spent"]) == Decimal("80.00")
    assert second.json()["customer_id"] == found["id"]


def test_customer_search_by_name(client, auth_headers):
    est = establishment(client, auth_headers, STORE)
    item = product(client, auth_headers, est["id"])
    name = f"Joaquim {random.randint(1000, 9999)}"
    _order(client, auth_headers, est["id"], item["id"], phone=_phone(), name=name)

    results = client.get(f"{API}/{est['id']}/customers", headers=auth_headers, params={"search": name.lower()}).json()

    assert [customer["name"] for customer in results] == [name]


def test_unknown_phone_lookup_returns_null(client, auth_headers):
    est = establishment(client, auth_headers, STORE)

    response = client.get(f"{API}/{est['id']}/customers/lookup", headers=auth_headers, params={"phone": "11900000000"})

    assert response.status_code == 200
    assert response.json() is None


# ------------------------------------------------------------------ cupons


def test_percent_coupon_discounts_the_order_and_counts_use(client, auth_headers):
    est = establishment(client, auth_headers, STORE)
    item = product(client, auth_headers, est["id"], price="50.00")
    code = f"DEZ{random.randint(1000, 9999)}"
    _coupon(client, auth_headers, est["id"], code=code, kind="PERCENT", value="10")

    response = _order(client, auth_headers, est["id"], item["id"], coupon_code=code.lower())

    assert response.status_code == 201, response.text
    assert Decimal(response.json()["discount"]) == Decimal("5.00")
    assert response.json()["coupon_code"] == code
    coupons = client.get(f"{API}/{est['id']}/coupons", headers=auth_headers).json()
    assert next(c for c in coupons if c["code"] == code)["uses"] == 1


def test_coupon_below_minimum_order_is_refused(client, auth_headers):
    est = establishment(client, auth_headers, STORE)
    item = product(client, auth_headers, est["id"], price="20.00")
    code = f"MIN{random.randint(1000, 9999)}"
    _coupon(client, auth_headers, est["id"], code=code, kind="FIXED", value="5", min_order="30")

    response = _order(client, auth_headers, est["id"], item["id"], coupon_code=code)

    assert response.status_code == 422
    assert "minimo" in response.json()["detail"].lower()


def test_used_up_or_expired_coupon_is_refused(client, auth_headers):
    est = establishment(client, auth_headers, STORE)
    item = product(client, auth_headers, est["id"], price="40.00")
    once = f"UMA{random.randint(1000, 9999)}"
    old = f"VELHO{random.randint(1000, 9999)}"
    _coupon(client, auth_headers, est["id"], code=once, kind="FIXED", value="5", max_uses=1)
    _coupon(client, auth_headers, est["id"], code=old, kind="FIXED", value="5", valid_until="2020-01-01")

    assert _order(client, auth_headers, est["id"], item["id"], coupon_code=once).status_code == 201
    assert _order(client, auth_headers, est["id"], item["id"], coupon_code=once).status_code == 422
    assert _order(client, auth_headers, est["id"], item["id"], coupon_code=old).status_code == 422


def test_coupon_preview_shows_discount(client, auth_headers):
    est = establishment(client, auth_headers, STORE)
    code = f"PREV{random.randint(1000, 9999)}"
    _coupon(client, auth_headers, est["id"], code=code, kind="FIXED", value="15")

    result = client.post(f"{API}/{est['id']}/coupons/validate", headers=auth_headers, json={"code": code, "subtotal": "60.00"}).json()

    assert result["valid"] is True
    assert Decimal(result["discount"]) == Decimal("15.00")


# ------------------------------------------------------------------ fidelidade


def test_loyalty_reward_after_goal_then_points_restart(client, auth_headers):
    est = establishment(client, auth_headers, STORE)
    _loyalty(client, auth_headers, est["id"], goal=2, reward="10.00")
    item = product(client, auth_headers, est["id"], price="40.00")
    phone = _phone()
    for _ in range(2):
        order = _order(client, auth_headers, est["id"], item["id"], phone=phone).json()
        finish(client, auth_headers, est["id"], order["id"], delivery=True)
    ready = client.get(f"{API}/{est['id']}/customers/lookup", headers=auth_headers, params={"phone": phone}).json()

    response = _order(client, auth_headers, est["id"], item["id"], phone=phone, use_loyalty_reward=True)

    assert ready["loyalty_points"] == 2
    assert ready["reward_available"] is True
    assert response.status_code == 201, response.text
    assert Decimal(response.json()["discount"]) == Decimal("10.00")
    after = client.get(f"{API}/{est['id']}/customers/lookup", headers=auth_headers, params={"phone": phone}).json()
    assert after["loyalty_points"] == 0


def test_loyalty_point_only_when_order_is_finished(client, auth_headers):
    est = establishment(client, auth_headers, STORE)
    _loyalty(client, auth_headers, est["id"], goal=10, reward="10.00")
    item = product(client, auth_headers, est["id"], price="40.00")
    phone = _phone()
    lookup = lambda: client.get(f"{API}/{est['id']}/customers/lookup", headers=auth_headers, params={"phone": phone}).json()  # noqa: E731

    order = _order(client, auth_headers, est["id"], item["id"], phone=phone).json()
    after_creation = lookup()["loyalty_points"]
    finish(client, auth_headers, est["id"], order["id"], delivery=True)

    assert after_creation == 0
    assert lookup()["loyalty_points"] == 1


def test_coupon_valid_until_today_in_store_timezone(client, auth_headers):
    est = establishment(client, auth_headers, STORE)
    item = product(client, auth_headers, est["id"], price="40.00")
    today_in_store = datetime.now(ZoneInfo("America/Sao_Paulo")).date().isoformat()
    code = f"HOJE{random.randint(1000, 9999)}"
    _coupon(client, auth_headers, est["id"], code=code, kind="FIXED", value="5", valid_until=today_in_store)

    assert _order(client, auth_headers, est["id"], item["id"], coupon_code=code).status_code == 201


def test_loyalty_reward_without_enough_points_is_refused(client, auth_headers):
    est = establishment(client, auth_headers, STORE)
    _loyalty(client, auth_headers, est["id"], goal=5, reward="10.00")
    item = product(client, auth_headers, est["id"], price="40.00")

    response = _order(client, auth_headers, est["id"], item["id"], phone=_phone(), use_loyalty_reward=True)

    assert response.status_code == 422


def test_canceling_gives_back_coupon_use_and_point(client, auth_headers):
    est = establishment(client, auth_headers, STORE)
    _loyalty(client, auth_headers, est["id"], goal=10, reward="10.00")
    item = product(client, auth_headers, est["id"], price="40.00")
    phone = _phone()
    code = f"VOLTA{random.randint(1000, 9999)}"
    _coupon(client, auth_headers, est["id"], code=code, kind="FIXED", value="5", max_uses=1)
    order = _order(client, auth_headers, est["id"], item["id"], phone=phone, coupon_code=code).json()

    cancel(client, auth_headers, est["id"], order["id"])

    customer = client.get(f"{API}/{est['id']}/customers/lookup", headers=auth_headers, params={"phone": phone}).json()
    assert customer["loyalty_points"] == 0
    assert _order(client, auth_headers, est["id"], item["id"], coupon_code=code).status_code == 201
