"""Taxa de entrega por bairro, motoboys e lucro por canal."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

from app.models.order import OrderSource
from tests.helpers import API, establishment, external_order, ingredient, product

STORE = "Smash House"


def _zone(client, headers, est_id, fee="8.00", active=True):
    response = client.post(f"{API}/{est_id}/delivery-zones", headers=headers,
                           json={"name": f"Bairro {uuid4().hex[:6]}", "fee": fee, "estimated_minutes": 40, "active": active})
    assert response.status_code == 201, response.text
    return response.json()


def _courier(client, headers, est_id, fee_per_delivery="6.00"):
    response = client.post(f"{API}/{est_id}/couriers", headers=headers,
                           json={"name": f"Moto {uuid4().hex[:4]}", "phone": "11999990000", "fee_per_delivery": fee_per_delivery})
    assert response.status_code == 201, response.text
    return response.json()


def _delivery(client, headers, est_id, product_id, **extra):
    payload = {
        "fulfillment_type": "DELIVERY", "payment_method": "PIX", "payment_status": "PAID",
        "customer_name": "Cliente", "delivery_address": "Rua A, 1",
        "items": [{"product_id": product_id, "quantity": 1}], **extra,
    }
    return client.post(f"{API}/{est_id}/orders", headers=headers, json=payload)


def _advance(client, headers, est_id, order_id, *statuses, courier_id=None):
    for status in statuses:
        body = {"status": status}
        if status == "OUT_FOR_DELIVERY" and courier_id:
            body["courier_id"] = courier_id
        response = client.patch(f"{API}/{est_id}/orders/{order_id}/status", headers=headers, json=body)
        assert response.status_code == 200, response.text
    return response.json()


# ------------------------------------------------------------------ bairros


def test_neighborhood_fee_is_charged_on_delivery(client, auth_headers):
    est = establishment(client, auth_headers, STORE)
    item = product(client, auth_headers, est["id"], price="40.00")
    zone = _zone(client, auth_headers, est["id"], fee="8.50")

    response = _delivery(client, auth_headers, est["id"], item["id"], delivery_zone_id=zone["id"])

    assert response.status_code == 201, response.text
    order = response.json()
    assert Decimal(order["delivery_fee"]) == Decimal("8.50")
    assert Decimal(order["total"]) == Decimal("48.50")
    assert order["neighborhood"] == zone["name"]


def test_typed_fee_wins_over_neighborhood_fee(client, auth_headers):
    est = establishment(client, auth_headers, STORE)
    item = product(client, auth_headers, est["id"], price="40.00")
    zone = _zone(client, auth_headers, est["id"], fee="8.50")

    order = _delivery(client, auth_headers, est["id"], item["id"], delivery_zone_id=zone["id"], delivery_fee="5.00").json()

    assert Decimal(order["delivery_fee"]) == Decimal("5.00")


def test_inactive_neighborhood_is_refused(client, auth_headers):
    est = establishment(client, auth_headers, STORE)
    item = product(client, auth_headers, est["id"])
    zone = _zone(client, auth_headers, est["id"], active=False)

    response = _delivery(client, auth_headers, est["id"], item["id"], delivery_zone_id=zone["id"])

    assert response.status_code == 422


# ------------------------------------------------------------------ motoboys


def test_courier_is_set_when_order_goes_out_for_delivery(client, auth_headers):
    est = establishment(client, auth_headers, STORE)
    item = product(client, auth_headers, est["id"])
    courier = _courier(client, auth_headers, est["id"])
    order = _delivery(client, auth_headers, est["id"], item["id"]).json()

    out = _advance(client, auth_headers, est["id"], order["id"], "ACCEPTED", "PREPARING", "READY", "OUT_FOR_DELIVERY", courier_id=courier["id"])

    assert out["courier_id"] == courier["id"]
    assert out["courier_name"] == courier["name"]


def test_courier_report_counts_deliveries_and_amount_to_pay(client, auth_headers):
    est = establishment(client, auth_headers, STORE)
    item = product(client, auth_headers, est["id"])
    zone = _zone(client, auth_headers, est["id"], fee="7.00")
    courier = _courier(client, auth_headers, est["id"], fee_per_delivery="6.00")
    start = datetime.now(timezone.utc) - timedelta(seconds=1)
    for _ in range(2):
        order = _delivery(client, auth_headers, est["id"], item["id"], delivery_zone_id=zone["id"]).json()
        _advance(client, auth_headers, est["id"], order["id"], "ACCEPTED", "PREPARING", "READY", "OUT_FOR_DELIVERY", courier_id=courier["id"])

    report = client.get(f"{API}/{est['id']}/couriers/report", headers=auth_headers,
                        params={"start": start.isoformat(), "end": (datetime.now(timezone.utc) + timedelta(seconds=1)).isoformat()}).json()

    row = next(r for r in report if r["courier_id"] == courier["id"])
    assert row["deliveries"] == 2
    assert Decimal(row["fees_charged"]) == Decimal("14.00")
    assert Decimal(row["to_pay"]) == Decimal("12.00")


# ------------------------------------------------------------------ lucro por canal


def test_profit_by_channel_discounts_commission_and_ingredient_cost(client, auth_headers):
    est = establishment(client, auth_headers, STORE)
    client.patch(f"{API}/{est['id']}", headers=auth_headers,
                 json={"channel_commissions": {"IFOOD": "20", "NINETY_NINE_FOOD": "15", "LOCAL": "0"}})
    meat = ingredient(client, auth_headers, est["id"], unit="kg", cost_per_unit="100.00")
    item = product(client, auth_headers, est["id"], price="50.00", ingredients=[{"ingredient_id": meat["id"], "quantity": "0.1"}])
    # Janela comeca agora: pedidos dos testes anteriores (mesma loja) ficam de fora
    start = datetime.now(timezone.utc)
    external_order(est["id"], OrderSource.IFOOD, item["id"])
    client.post(f"{API}/{est['id']}/orders", headers=auth_headers, json={
        "fulfillment_type": "COUNTER", "payment_method": "CASH", "items": [{"product_id": item["id"], "quantity": 1}]})

    report = client.get(f"{API}/{est['id']}/reports/profit-by-channel", headers=auth_headers,
                        params={"start": start.isoformat(), "end": (datetime.now(timezone.utc) + timedelta(seconds=1)).isoformat()}).json()

    rows = {row["channel"]: row for row in report}
    assert (Decimal(rows["IFOOD"]["revenue"]), Decimal(rows["IFOOD"]["commission"]), Decimal(rows["IFOOD"]["ingredient_cost"]),
            Decimal(rows["IFOOD"]["profit"])) == (Decimal("50.00"), Decimal("10.00"), Decimal("10.00"), Decimal("30.00"))
    assert Decimal(rows["LOCAL"]["profit"]) == Decimal("40.00")
    assert rows["LOCAL"]["orders"] == 1
