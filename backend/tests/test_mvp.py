from __future__ import annotations

from app.models.order import OrderStatus


def test_login_and_establishments(client):
    response = client.post("/api/v1/auth/login", json={"email": "admin@comandahub.local", "password": "demo123"})
    assert response.status_code == 200
    data = response.json()
    assert data["access_token"]
    assert len(data["user"]["establishments"]) == 3


def test_establishment_isolation(client):
    login = client.post("/api/v1/auth/login", json={"email": "burger@comandahub.local", "password": "demo123"}).json()
    headers = {"Authorization": f"Bearer {login['access_token']}"}
    establishments = client.get("/api/v1/establishments", headers=headers).json()
    assert len(establishments) == 1
    forbidden_id = next(est["id"] for est in client.post("/api/v1/auth/login", json={"email": "admin@comandahub.local", "password": "demo123"}).json()["user"]["establishments"] if est["name"] == "Smash House")
    assert client.get(f"/api/v1/establishments/{forbidden_id}/orders", headers=headers).status_code == 403


def test_create_local_order_and_total(client, auth_headers):
    establishment = client.get("/api/v1/establishments", headers=auth_headers).json()[0]
    products = client.get(f"/api/v1/establishments/{establishment['id']}/products", headers=auth_headers).json()
    payload = {
        "customer_name": "Teste Local",
        "fulfillment_type": "COUNTER",
        "payment_method": "CARD",
        "payment_status": "PAID",
        "items": [{"product_id": products[0]["id"], "quantity": 2, "option_ids": []}],
    }
    response = client.post(f"/api/v1/establishments/{establishment['id']}/orders", headers=auth_headers, json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["source"] == "COUNTER"
    assert float(data["total"]) > 0


def test_simulate_external_order_and_transition(client, auth_headers):
    establishment = client.get("/api/v1/establishments", headers=auth_headers).json()[0]
    response = client.post(
        f"/api/v1/dev/establishments/{establishment['id']}/simulate-order",
        headers=auth_headers,
        json={"source": "IFOOD", "quantity": 1},
    )
    assert response.status_code == 201
    order = response.json()[0]
    accepted = client.patch(
        f"/api/v1/establishments/{establishment['id']}/orders/{order['id']}/status",
        headers=auth_headers,
        json={"status": "ACCEPTED"},
    )
    assert accepted.status_code == 200
    assert accepted.json()["status"] == OrderStatus.ACCEPTED.value


def test_invalid_status_transition_is_rejected(client, auth_headers):
    establishment = client.get("/api/v1/establishments", headers=auth_headers).json()[0]
    order = client.post(
        f"/api/v1/dev/establishments/{establishment['id']}/simulate-order",
        headers=auth_headers,
        json={"source": "OWN_DELIVERY", "quantity": 1},
    ).json()[0]
    response = client.patch(
        f"/api/v1/establishments/{establishment['id']}/orders/{order['id']}/status",
        headers=auth_headers,
        json={"status": "FINISHED"},
    )
    assert response.status_code == 422
