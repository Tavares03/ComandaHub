"""Perfis: a cozinha so ve o preparo; dados de clientes, caixa e financeiro ficam com atendimento/gerencia."""
from __future__ import annotations

import pytest

from tests.helpers import API, establishment, local_order, product

STORE = "Burger Station"


@pytest.mark.parametrize(
    "path",
    [
        "dashboard",
        "customers",
        "customers/lookup?phone=11999999999",
        "coupons",
        "cash/current",
        "cash/sessions",
        "reports/overview",
        "reports/profit-by-channel",
        "couriers/report",
        "users",
    ],
)
def test_kitchen_cannot_read_customers_cash_or_finance(client, auth_headers, kitchen_headers, path):
    est = establishment(client, auth_headers, STORE)

    assert client.get(f"{API}/{est['id']}/{path}", headers=kitchen_headers).status_code == 403


@pytest.mark.parametrize("path", ["orders/board", "orders/pending-count", "products", "ingredients"])
def test_kitchen_still_sees_what_it_needs(client, auth_headers, kitchen_headers, path):
    est = establishment(client, auth_headers, STORE)

    assert client.get(f"{API}/{est['id']}/{path}", headers=kitchen_headers).status_code == 200


@pytest.mark.parametrize(
    "path,expected",
    [
        ("dashboard", 200),
        ("customers", 200),
        ("cash/current", 200),
        ("reports/overview", 403),
        ("reports/profit-by-channel", 403),
        ("couriers/report", 403),
        ("users", 403),
    ],
)
def test_attendant_runs_the_store_but_finance_is_admin_only(client, auth_headers, attendant_headers, path, expected):
    est = establishment(client, auth_headers, STORE)

    assert client.get(f"{API}/{est['id']}/{path}", headers=attendant_headers).status_code == expected


def test_pending_count_counts_new_orders(client, auth_headers):
    est = establishment(client, auth_headers, STORE)
    item = product(client, auth_headers, est["id"])
    before = client.get(f"{API}/{est['id']}/orders/pending-count", headers=auth_headers).json()["new_orders"]

    assert local_order(client, auth_headers, est["id"], item["id"]).status_code == 201

    after = client.get(f"{API}/{est['id']}/orders/pending-count", headers=auth_headers).json()["new_orders"]
    assert after == before + 1


def test_api_dates_always_carry_timezone(client, auth_headers):
    # SQLite guarda datas sem fuso; sem o UTCDateTime a API mandava "2026-11-09T00:10:53" e o
    # navegador lia como horario local (tempo de fila errado em 3h no Brasil)
    est = establishment(client, auth_headers, STORE)
    item = product(client, auth_headers, est["id"])
    order = local_order(client, auth_headers, est["id"], item["id"]).json()

    fetched = client.get(f"{API}/{est['id']}/orders/{order['id']}", headers=auth_headers).json()

    for value in (fetched["created_at"], fetched["updated_at"], fetched["events"][0]["created_at"]):
        assert value.endswith(("Z", "+00:00")), value
