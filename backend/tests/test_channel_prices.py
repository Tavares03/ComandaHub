"""Preco diferente por canal (ex.: mais caro no iFood por causa da comissao)."""
from __future__ import annotations

from decimal import Decimal

from app.models.order import OrderSource
from tests.helpers import API, establishment, external_order, get_product, local_order, product


def test_channel_price_is_charged_only_on_that_channel(client, auth_headers):
    est = establishment(client, auth_headers)
    burger = product(client, auth_headers, est["id"], price="30.00", channel_prices={"IFOOD": "36.90"})

    ifood = external_order(est["id"], OrderSource.IFOOD, burger["id"])
    ninety_nine = external_order(est["id"], OrderSource.NINETY_NINE_FOOD, burger["id"])
    local = local_order(client, auth_headers, est["id"], burger["id"]).json()

    assert ifood.items[0].unit_price == Decimal("36.90")
    assert ninety_nine.items[0].unit_price == Decimal("30.00")
    assert Decimal(local["items"][0]["unit_price"]) == Decimal("30.00")


def test_channel_price_is_listed_with_the_product(client, auth_headers):
    est = establishment(client, auth_headers)
    burger = product(client, auth_headers, est["id"], price="30.00", channel_prices={"NINETY_NINE_FOOD": "33.00"})

    assert get_product(client, auth_headers, est["id"], burger["id"])["channel_prices"] == {"NINETY_NINE_FOOD": "33.00"}


def test_bulk_markup_rounds_up_to_ninety_cents(client, auth_headers):
    est = establishment(client, auth_headers)
    burger = product(client, auth_headers, est["id"], price="30.00")

    response = client.post(f"{API}/{est['id']}/channel-prices", headers=auth_headers,
                           json={"channel": "IFOOD", "percent": "20", "round_to_90": True, "product_ids": [burger["id"]]})

    assert response.status_code == 200, response.text
    # 30,00 + 20% = 36,00 -> arredonda para cima ate ,90
    assert get_product(client, auth_headers, est["id"], burger["id"])["channel_prices"] == {"IFOOD": "36.90"}


def test_bulk_without_percent_removes_channel_price(client, auth_headers):
    est = establishment(client, auth_headers)
    burger = product(client, auth_headers, est["id"], price="30.00", channel_prices={"IFOOD": "36.90", "LOCAL": "29.00"})

    client.post(f"{API}/{est['id']}/channel-prices", headers=auth_headers,
                json={"channel": "IFOOD", "percent": None, "product_ids": [burger["id"]]})

    assert get_product(client, auth_headers, est["id"], burger["id"])["channel_prices"] == {"LOCAL": "29.00"}
