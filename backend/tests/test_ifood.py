"""Integracao iFood com um cliente falso (nada sai para a internet)."""
from __future__ import annotations

import copy
from decimal import Decimal
from uuid import uuid4

import pytest

import app.api.v1.endpoints.integrations as integrations_endpoint
import app.db as db_module
import app.integrations.ifood.service as ifood_service
from app.integrations.ifood.client import IfoodError
from app.integrations.ifood.mapper import parse_order
from app.integrations.ifood.poller import poll_once
from app.models.order import FulfillmentType, PaymentMethod, PaymentStatus
from tests.helpers import API, establishment, product

STORE = "Smash House"
MERCHANT = "merchant-smash-test"

SAMPLE_ORDER = {
    "id": "ifood-order-1",
    "displayId": "4231",
    "orderType": "DELIVERY",
    "orderTiming": "IMMEDIATE",
    "isTest": True,
    "merchant": {"id": MERCHANT, "name": "Smash no iFood"},
    "customer": {"name": "Cliente iFood", "phone": {"number": "0800 700 1234", "localizer": "55667788"}},
    "items": [
        {
            "name": "Item Que Nao Existe Aqui",
            "quantity": 2,
            "unitPrice": 20.0,
            "optionsPrice": 3.0,
            "totalPrice": 46.0,
            "observations": "sem cebola",
            "options": [{"name": "Bacon", "quantity": 1, "unitPrice": 3.0, "groupName": "Adicionais"}],
        }
    ],
    "total": {"subTotal": 46.0, "deliveryFee": 6.99, "benefits": 5.0, "orderAmount": 47.99, "additionalFees": 0},
    "payments": {"prepaid": 47.99, "pending": 0, "methods": [{"value": 47.99, "method": "CREDIT", "type": "ONLINE", "prepaid": True}]},
    "delivery": {
        "deliveredBy": "IFOOD",
        "observations": "Portao azul",
        "pickupCode": "9876",
        "deliveryAddress": {
            "formattedAddress": "Rua das Flores, 100",
            "complement": "Apto 12",
            "reference": "Perto da padaria",
            "neighborhood": "Centro",
        },
    },
}


class FakeIfood:
    def __init__(self) -> None:
        self.orders: dict[str, dict] = {}
        self.merchant_list = [{"id": MERCHANT, "name": "Smash no iFood"}, {"id": "merchant-outra", "name": "Outra loja"}]
        self.calls: list[tuple] = []
        self.fail_on: set[str] = set()
        self.events: list[dict] = []
        self.acked: list[str] = []

    def _call(self, name: str, *args) -> None:
        self.calls.append((name, *args))
        if name in self.fail_on:
            raise IfoodError("Pedido ja cancelado no iFood", 400)

    def merchants(self):
        return self.merchant_list

    def merchant_status(self, merchant_id):
        return [{"available": True, "message": {"title": "Loja aberta", "subtitle": ""}}]

    def order(self, order_id):
        return copy.deepcopy(self.orders[order_id])

    def confirm(self, order_id):
        self._call("confirm", order_id)

    def start_preparation(self, order_id):
        self._call("start_preparation", order_id)

    def ready_to_pickup(self, order_id):
        self._call("ready_to_pickup", order_id)

    def dispatch(self, order_id):
        self._call("dispatch", order_id)

    def cancellation_reasons(self, order_id):
        return [{"cancelCodeId": "501", "description": "PROBLEMAS DE SISTEMA"}, {"cancelCodeId": "503", "description": "ITEM INDISPONIVEL"}]

    def request_cancellation(self, order_id, code, reason):
        self._call("request_cancellation", order_id, code, reason)

    def poll_events(self, merchant_ids):
        events, self.events = self.events, []
        return [event for event in events if event.get("merchantId") in merchant_ids]

    def acknowledge(self, event_ids):
        self.acked.extend(event_ids)


@pytest.fixture()
def fake(monkeypatch):
    fake = FakeIfood()
    monkeypatch.setattr(ifood_service, "get_ifood_client", lambda: fake)
    monkeypatch.setattr(integrations_endpoint, "get_ifood_client", lambda: fake)
    return fake


@pytest.fixture()
def linked(client, auth_headers, fake):
    est = establishment(client, auth_headers, STORE)
    response = client.put(f"{API}/{est['id']}/integrations/ifood", headers=auth_headers, json={"merchant_id": MERCHANT})
    assert response.status_code == 200, response.text
    yield est
    client.put(f"{API}/{est['id']}/integrations/ifood", headers=auth_headers, json={"merchant_id": None})


def _new_order(fake, **changes) -> dict:
    raw = copy.deepcopy(SAMPLE_ORDER)
    raw["id"] = f"ifood-{uuid4().hex[:10]}"
    raw.update(changes)
    fake.orders[raw["id"]] = raw
    return raw


def _event(raw, code="PLC", full_code="PLACED", merchant=MERCHANT) -> dict:
    return {"id": f"evt-{uuid4().hex[:8]}", "code": code, "fullCode": full_code, "orderId": raw["id"], "merchantId": merchant}


def _process(fake, *events) -> list[str]:
    with db_module.SessionLocal() as db:
        return ifood_service.process_events(db, fake, list(events))


def _board_order(client, headers, est_id, external_display_id):
    items = client.get(f"{API}/{est_id}/orders/board", headers=headers).json()["items"]
    return next(order for order in items if order["external_display_id"] == external_display_id)


# ------------------------------------------------------------------ conversao do pedido


def test_parse_order_keeps_ifood_prices_and_delivery_details():
    data = parse_order(SAMPLE_ORDER, "America/Sao_Paulo")

    assert data.external_id == "ifood-order-1"
    assert data.display_id == "4231"
    assert data.fulfillment_type == FulfillmentType.DELIVERY
    assert data.marketplace_delivery is True
    assert (data.payment_method, data.payment_status) == (PaymentMethod.ONLINE, PaymentStatus.PAID)
    assert (data.subtotal, data.delivery_fee, data.discount, data.total) == (Decimal("46.00"), Decimal("6.99"), Decimal("5.00"), Decimal("47.99"))
    assert data.items[0].unit_price == Decimal("23.00")
    assert data.items[0].options[0].group_name == "Adicionais"
    assert data.delivery_address == "Rua das Flores, 100 - Apto 12 - Ref.: Perto da padaria - Centro"
    assert "Codigo de coleta: 9876" in data.notes and "PEDIDO DE TESTE" in data.notes


def test_parse_cash_on_delivery_and_takeout():
    cash = copy.deepcopy(SAMPLE_ORDER)
    cash["payments"] = {"prepaid": 0, "pending": 47.99,
                        "methods": [{"value": 47.99, "method": "CASH", "type": "OFFLINE", "cash": {"changeFor": 100}}]}
    takeout = copy.deepcopy(SAMPLE_ORDER)
    takeout["orderType"] = "TAKEOUT"

    cash_data, takeout_data = parse_order(cash), parse_order(takeout)

    assert (cash_data.payment_method, cash_data.payment_status) == (PaymentMethod.CASH, PaymentStatus.PENDING)
    assert "Troco para R$ 100.00" in cash_data.notes
    assert takeout_data.fulfillment_type == FulfillmentType.PICKUP
    assert takeout_data.delivery_address is None and takeout_data.marketplace_delivery is False


# ------------------------------------------------------------------ vinculo da loja


def test_link_requires_authorized_merchant_and_is_unique(client, auth_headers, fake, linked):
    other = establishment(client, auth_headers, "Burger Station")

    unknown = client.put(f"{API}/{other['id']}/integrations/ifood", headers=auth_headers, json={"merchant_id": "nao-autorizado"})
    taken = client.put(f"{API}/{other['id']}/integrations/ifood", headers=auth_headers, json={"merchant_id": MERCHANT})
    status = client.get(f"{API}/{linked['id']}/integrations/ifood", headers=auth_headers).json()

    assert unknown.status_code == 422
    assert taken.status_code == 409
    assert status["merchant_name"] == "Smash no iFood"
    assert status["store_status"]["available"] is True


def test_only_admin_manages_ifood_link(client, auth_headers, attendant_headers, fake):
    burger = establishment(client, auth_headers, "Burger Station")

    assert client.get(f"{API}/{burger['id']}/integrations/ifood", headers=attendant_headers).status_code == 403
    assert client.put(f"{API}/{burger['id']}/integrations/ifood", headers=attendant_headers, json={"merchant_id": MERCHANT}).status_code == 403


# ------------------------------------------------------------------ eventos iFood -> ComandaHub


def test_placed_event_creates_order_with_ifood_prices(client, auth_headers, fake, linked):
    known = product(client, auth_headers, linked["id"], price="99.00", name=f"Burger iFood {uuid4().hex[:4]}")
    raw = _new_order(fake)
    raw["items"].append({"name": known["name"].upper(), "quantity": 1, "unitPrice": 30.0, "totalPrice": 30.0})

    acked = _process(fake, _event(raw), _event(raw))  # evento repetido nao duplica

    order = _board_order(client, auth_headers, linked["id"], raw["displayId"])
    assert len(acked) == 2
    assert order["integration"] == "IFOOD" and order["source"] == "IFOOD"
    assert Decimal(order["total"]) == Decimal("47.99")
    assert order["marketplace_delivery"] is True
    unknown_item, known_item = order["items"]
    assert unknown_item["product_id"] is None and Decimal(unknown_item["unit_price"]) == Decimal("23.00")
    assert known_item["product_id"] == known["id"] and Decimal(known_item["unit_price"]) == Decimal("30.00")
    same_number = client.get(f"{API}/{linked['id']}/orders", headers=auth_headers, params={"search": order["order_number"]}).json()
    assert same_number["total"] == 1


def test_status_events_move_and_cancel_the_order(client, auth_headers, fake, linked):
    raw = _new_order(fake, displayId=f"C{uuid4().hex[:4]}")
    _process(fake, _event(raw), _event(raw, "CFM", "CONFIRMED"))
    confirmed = _board_order(client, auth_headers, linked["id"], raw["displayId"])

    _process(fake, _event(raw, "CAN", "CANCELLED"))
    canceled = client.get(f"{API}/{linked['id']}/orders/{confirmed['id']}", headers=auth_headers).json()

    assert confirmed["status"] == "ACCEPTED"
    assert canceled["status"] == "CANCELED"


def test_event_from_unlinked_merchant_is_acknowledged_and_ignored(fake, linked):
    raw = _new_order(fake)

    acked = _process(fake, _event(raw, merchant="merchant-desconhecido"))

    assert len(acked) == 1


def test_poll_once_processes_and_acknowledges(client, auth_headers, fake, linked):
    raw = _new_order(fake, displayId=f"P{uuid4().hex[:4]}")
    event = _event(raw)
    fake.events = [event]

    assert poll_once(fake) == 1
    assert fake.acked == [event["id"]]
    assert _board_order(client, auth_headers, linked["id"], raw["displayId"])["status"] == "NEW"


# ------------------------------------------------------------------ ComandaHub -> iFood


def _imported(client, headers, fake, est, **changes):
    raw = _new_order(fake, displayId=f"S{uuid4().hex[:4]}", **changes)
    _process(fake, _event(raw))
    return raw, _board_order(client, headers, est["id"], raw["displayId"])


def _set_status(client, headers, est_id, order_id, status, **extra):
    return client.patch(f"{API}/{est_id}/orders/{order_id}/status", headers=headers, json={"status": status, **extra})


def test_accepting_confirms_on_ifood_and_failure_keeps_status(client, auth_headers, fake, linked):
    raw, order = _imported(client, auth_headers, fake, linked)
    fake.fail_on = {"confirm"}

    refused = _set_status(client, auth_headers, linked["id"], order["id"], "ACCEPTED")
    fake.fail_on = set()
    accepted = _set_status(client, auth_headers, linked["id"], order["id"], "ACCEPTED")

    assert refused.status_code == 502 and "iFood" in refused.json()["detail"]
    assert accepted.status_code == 200 and accepted.json()["status"] == "ACCEPTED"
    assert ("confirm", raw["id"]) in fake.calls


def test_ifood_delivery_is_ready_to_pickup_and_cannot_be_dispatched_by_store(client, auth_headers, fake, linked):
    raw, order = _imported(client, auth_headers, fake, linked)
    for status in ("ACCEPTED", "PREPARING", "READY"):
        assert _set_status(client, auth_headers, linked["id"], order["id"], status).status_code == 200

    dispatch = _set_status(client, auth_headers, linked["id"], order["id"], "OUT_FOR_DELIVERY")

    assert ("ready_to_pickup", raw["id"]) in fake.calls
    assert dispatch.status_code == 422


def test_store_delivery_dispatches_on_ifood(client, auth_headers, fake, linked):
    delivery = copy.deepcopy(SAMPLE_ORDER["delivery"]) | {"deliveredBy": "MERCHANT"}
    raw, order = _imported(client, auth_headers, fake, linked, delivery=delivery)
    for status in ("ACCEPTED", "PREPARING", "READY", "OUT_FOR_DELIVERY"):
        assert _set_status(client, auth_headers, linked["id"], order["id"], status).status_code == 200

    assert ("dispatch", raw["id"]) in fake.calls
    assert ("ready_to_pickup", raw["id"]) not in fake.calls


def test_cancel_needs_ifood_reason_and_waits_for_confirmation(client, auth_headers, fake, linked):
    raw, order = _imported(client, auth_headers, fake, linked)
    reasons = client.get(f"{API}/{linked['id']}/orders/{order['id']}/ifood/cancellation-reasons", headers=auth_headers).json()

    no_code = _set_status(client, auth_headers, linked["id"], order["id"], "CANCELED", cancel_reason="Acabou o pao")
    requested = _set_status(client, auth_headers, linked["id"], order["id"], "CANCELED", cancel_reason="Acabou o pao", cancel_code="503")
    _process(fake, _event(raw, "CAN", "CANCELLED"))
    final = client.get(f"{API}/{linked['id']}/orders/{order['id']}", headers=auth_headers).json()

    assert reasons[0] == {"code": "501", "description": "PROBLEMAS DE SISTEMA"}
    assert no_code.status_code == 422
    assert requested.status_code == 200 and requested.json()["status"] == "NEW"
    assert ("request_cancellation", raw["id"], "503", "Acabou o pao") in fake.calls
    assert final["status"] == "CANCELED"


def test_simulated_ifood_orders_never_call_ifood(client, auth_headers, fake):
    burger = establishment(client, auth_headers, "Burger Station")
    simulated = client.post(f"/api/v1/dev/establishments/{burger['id']}/simulate-order", headers=auth_headers, json={"source": "IFOOD"}).json()[0]

    response = _set_status(client, auth_headers, burger["id"], simulated["id"], "ACCEPTED")

    assert response.status_code == 200
    assert simulated["integration"] is None
    assert fake.calls == []
