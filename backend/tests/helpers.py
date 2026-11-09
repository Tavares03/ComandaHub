"""Atalhos usados pelos testes de API (cada teste cria seus proprios produtos com nomes unicos)."""
from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import app.db as db_module
from app.connectors.base import NormalizedOrder, NormalizedOrderItem
from app.models.order import FulfillmentType, OrderSource, PaymentMethod, PaymentStatus
from app.services.order_service import create_external_order

API = "/api/v1/establishments"


def establishment(client, headers, name="Burger Station"):
    return next(e for e in client.get(API, headers=headers).json() if e["name"] == name)


def category_id(client, headers, establishment_id):
    return client.get(f"{API}/{establishment_id}/categories", headers=headers).json()[0]["id"]


def product(client, headers, establishment_id, groups=(), price="30.00", name=None, ingredients=(), **extra):
    payload = {
        "category_id": category_id(client, headers, establishment_id),
        "name": name or f"Teste {uuid4().hex[:8]}",
        "price": price,
        "option_groups": list(groups),
        "ingredients": list(ingredients),
        **extra,
    }
    response = client.post(f"{API}/{establishment_id}/products", headers=headers, json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def get_product(client, headers, establishment_id, product_id):
    products = client.get(f"{API}/{establishment_id}/products", headers=headers).json()
    return next(item for item in products if item["id"] == product_id)


def option(product_json, group_name, option_name):
    group = next(g for g in product_json["option_groups"] if g["name"] == group_name)
    return next(o for o in group["options"] if o["name"] == option_name)


def ingredient(client, headers, establishment_id, name=None, **fields):
    body = {"name": name or f"Insumo {uuid4().hex[:6]}", **fields}
    response = client.post(f"{API}/{establishment_id}/ingredients", headers=headers, json=body)
    assert response.status_code == 201, response.text
    return response.json()


def get_ingredient(client, headers, establishment_id, ingredient_id):
    items = client.get(f"{API}/{establishment_id}/ingredients", headers=headers).json()
    return next(item for item in items if item["id"] == ingredient_id)


def local_order(client, headers, establishment_id, product_id, option_ids=(), quantity=1, **extra):
    payload = {
        "fulfillment_type": "COUNTER",
        "payment_method": "CASH",
        "items": [{"product_id": product_id, "quantity": quantity, "options": [{"option_id": oid} for oid in option_ids]}],
        **extra,
    }
    return client.post(f"{API}/{establishment_id}/orders", headers=headers, json=payload)


def external_order(establishment_id, source, product_id, option_ids=(), quantity=1):
    normalized = NormalizedOrder(
        external_order_id=f"TEST-{uuid4().hex[:10]}",
        source=source,
        customer_name="Teste",
        customer_phone=None,
        delivery_address="Rua Teste, 1",
        fulfillment_type=FulfillmentType.DELIVERY,
        payment_method=PaymentMethod.ONLINE,
        payment_status=PaymentStatus.PAID,
        delivery_fee=Decimal("0.00"),
        discount=Decimal("0.00"),
        notes=None,
        items=[NormalizedOrderItem(product_id=product_id, quantity=quantity, option_ids=list(option_ids), notes=None)],
        raw_payload={},
    )
    # conftest troca app.db.SessionLocal pela sessao do banco de teste
    with db_module.SessionLocal() as db:
        return create_external_order(db, establishment_id, normalized)


def login(client, email, password):
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def finish(client, headers, establishment_id, order_id, delivery=False):
    """Leva o pedido ate FINALIZADO pelo fluxo normal."""
    steps = ["ACCEPTED", "PREPARING", "READY", *(["OUT_FOR_DELIVERY"] if delivery else []), "FINISHED"]
    for status in steps:
        response = client.patch(f"{API}/{establishment_id}/orders/{order_id}/status", headers=headers, json={"status": status})
        assert response.status_code == 200, response.text
    return response.json()


def cancel(client, headers, establishment_id, order_id):
    return client.patch(f"{API}/{establishment_id}/orders/{order_id}/status", headers=headers,
                        json={"status": "CANCELED", "cancel_reason": "Teste"})


__all__ = ["API", "OrderSource", "uuid4", "Decimal"]
