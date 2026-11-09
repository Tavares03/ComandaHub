"""Caixa: abertura, vendas do turno por forma de pagamento, sangria/reforco e fechamento com diferenca."""
from __future__ import annotations

from decimal import Decimal

from tests.helpers import API, cancel, establishment, product

STORE = "Smash House"


def _cash(client, headers, est_id, path="", method="get", **body):
    url = f"{API}/{est_id}/cash{path}"
    return client.get(url, headers=headers) if method == "get" else client.post(url, headers=headers, json=body)


def _fresh_session(client, headers, est_id, opening="100.00"):
    """Fecha o caixa que tiver ficado aberto e abre um novo."""
    if _cash(client, headers, est_id, "/current").json():
        _cash(client, headers, est_id, "/close", "post", counted_amount="0")
    response = _cash(client, headers, est_id, "/open", "post", opening_amount=opening)
    assert response.status_code == 201, response.text
    return response.json()


def _sell(client, headers, est_id, product_id, method, quantity=1):
    response = client.post(f"{API}/{est_id}/orders", headers=headers, json={
        "fulfillment_type": "COUNTER", "payment_method": method, "payment_status": "PAID",
        "items": [{"product_id": product_id, "quantity": quantity}],
    })
    assert response.status_code == 201, response.text
    return response.json()


def test_open_cash_shows_as_current_and_cannot_open_twice(client, auth_headers):
    est = establishment(client, auth_headers, STORE)
    _fresh_session(client, auth_headers, est["id"], opening="150.00")

    current = _cash(client, auth_headers, est["id"], "/current").json()
    again = _cash(client, auth_headers, est["id"], "/open", "post", opening_amount="10")

    assert Decimal(current["opening_amount"]) == Decimal("150.00")
    assert current["opened_by_name"] == "Admin Demo"
    assert again.status_code == 409


def test_sales_of_the_shift_are_grouped_by_payment_method(client, auth_headers):
    est = establishment(client, auth_headers, STORE)
    item = product(client, auth_headers, est["id"], price="20.00")
    _fresh_session(client, auth_headers, est["id"])
    _sell(client, auth_headers, est["id"], item["id"], "CASH")
    _sell(client, auth_headers, est["id"], item["id"], "PIX", quantity=2)
    canceled = _sell(client, auth_headers, est["id"], item["id"], "CARD")
    cancel(client, auth_headers, est["id"], canceled["id"])

    summary = _cash(client, auth_headers, est["id"], "/current").json()

    by_method = {row["payment_method"]: (row["orders"], Decimal(row["total"])) for row in summary["sales_by_method"]}
    assert by_method == {"CASH": (1, Decimal("20.00")), "PIX": (1, Decimal("40.00"))}
    assert Decimal(summary["total_sales"]) == Decimal("60.00")
    assert summary["canceled_count"] == 1


def test_expected_cash_counts_change_sales_withdrawals_and_supplies(client, auth_headers):
    est = establishment(client, auth_headers, STORE)
    item = product(client, auth_headers, est["id"], price="30.00")
    _fresh_session(client, auth_headers, est["id"], opening="100.00")
    _sell(client, auth_headers, est["id"], item["id"], "CASH")
    _sell(client, auth_headers, est["id"], item["id"], "CARD")
    assert _cash(client, auth_headers, est["id"], "/movements", "post", kind="WITHDRAWAL", amount="50", note="Deposito").status_code == 201
    _cash(client, auth_headers, est["id"], "/movements", "post", kind="SUPPLY", amount="20", note="Troco extra")

    summary = _cash(client, auth_headers, est["id"], "/current").json()

    # 100 (troco) + 30 (dinheiro) - 50 (sangria) + 20 (reforco)
    assert Decimal(summary["expected_cash"]) == Decimal("100.00")
    assert [m["kind"] for m in summary["movements"]] == ["WITHDRAWAL", "SUPPLY"]


def test_closing_records_counted_amount_and_difference(client, auth_headers):
    est = establishment(client, auth_headers, STORE)
    item = product(client, auth_headers, est["id"], price="25.00")
    session = _fresh_session(client, auth_headers, est["id"], opening="50.00")
    _sell(client, auth_headers, est["id"], item["id"], "CASH")

    response = _cash(client, auth_headers, est["id"], "/close", "post", counted_amount="70.00", notes="Faltou troco")

    assert response.status_code == 200, response.text
    closed = response.json()
    assert Decimal(closed["expected_cash"]) == Decimal("75.00")
    assert Decimal(closed["difference"]) == Decimal("-5.00")
    assert _cash(client, auth_headers, est["id"], "/current").json() is None
    history = _cash(client, auth_headers, est["id"], "/sessions").json()
    assert history[0]["id"] == session["id"]
    assert history[0]["closed_at"] is not None


def test_closing_without_open_cash_is_refused(client, auth_headers):
    est = establishment(client, auth_headers, STORE)
    if _cash(client, auth_headers, est["id"], "/current").json():
        _cash(client, auth_headers, est["id"], "/close", "post", counted_amount="0")

    response = _cash(client, auth_headers, est["id"], "/close", "post", counted_amount="0")

    assert response.status_code == 409


def test_kitchen_cannot_open_cash(client, auth_headers):
    est = establishment(client, auth_headers, STORE)
    login = client.post("/api/v1/auth/login", json={"email": "cozinha@comandahub.local", "password": "demo123"})
    kitchen = {"Authorization": f"Bearer {login.json()['access_token']}"}

    response = _cash(client, kitchen, est["id"], "/open", "post", opening_amount="10")

    assert response.status_code == 403
