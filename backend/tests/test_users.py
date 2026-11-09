"""Usuarios da loja (gerencia cria, muda perfil, redefine senha e remove), troca da propria senha e login."""
from __future__ import annotations

from uuid import uuid4

from tests.helpers import API, establishment, login

STORE = "Burger Station"


def _email() -> str:
    return f"func-{uuid4().hex[:8]}@exemplo.com.br"


def _add(client, headers, est_id, email=None, role="ATTENDANT", password="segredo123", name="Funcionario Teste"):
    return client.post(f"{API}/{est_id}/users", headers=headers,
                       json={"name": name, "email": email or _email(), "password": password, "role": role})


def test_admin_creates_user_who_can_log_in(client, auth_headers):
    est = establishment(client, auth_headers, STORE)
    email = _email()

    response = _add(client, auth_headers, est["id"], email=email, role="KITCHEN")

    assert response.status_code == 201, response.text
    assert response.json()["role"] == "KITCHEN"
    me = client.get("/api/v1/auth/me", headers=login(client, email, "segredo123")).json()
    assert [(e["name"], e["role"]) for e in me["establishments"]] == [(STORE, "KITCHEN")]


def test_existing_email_gets_access_and_keeps_password(client, auth_headers):
    burger = establishment(client, auth_headers, STORE)
    smash = establishment(client, auth_headers, "Smash House")
    email = _email()
    _add(client, auth_headers, burger["id"], email=email, password="senha-original")

    response = _add(client, auth_headers, smash["id"], email=email.upper(), password="outra-senha")

    assert response.status_code == 201, response.text
    headers = login(client, email, "senha-original")
    names = {e["name"] for e in client.get("/api/v1/auth/me", headers=headers).json()["establishments"]}
    assert names == {STORE, "Smash House"}
    assert _add(client, auth_headers, smash["id"], email=email).status_code == 409


def test_invalid_email_or_short_password_is_refused(client, auth_headers):
    est = establishment(client, auth_headers, STORE)

    assert _add(client, auth_headers, est["id"], email="sem-arroba").status_code == 422
    assert _add(client, auth_headers, est["id"], password="123").status_code == 422


def test_admin_changes_role_and_resets_password(client, auth_headers):
    est = establishment(client, auth_headers, STORE)
    email = _email()
    user = _add(client, auth_headers, est["id"], email=email).json()

    response = client.patch(f"{API}/{est['id']}/users/{user['id']}", headers=auth_headers,
                            json={"role": "ADMIN", "password": "nova-senha-1"})

    assert response.status_code == 200, response.text
    assert response.json()["role"] == "ADMIN"
    login(client, email, "nova-senha-1")


def test_admin_cannot_change_own_role_or_remove_self(client, auth_headers):
    est = establishment(client, auth_headers, STORE)
    me = client.get("/api/v1/auth/me", headers=auth_headers).json()

    assert client.patch(f"{API}/{est['id']}/users/{me['id']}", headers=auth_headers, json={"role": "KITCHEN"}).status_code == 422
    assert client.delete(f"{API}/{est['id']}/users/{me['id']}", headers=auth_headers).status_code == 422


def test_removed_user_loses_access_to_the_store(client, auth_headers):
    est = establishment(client, auth_headers, STORE)
    email = _email()
    user = _add(client, auth_headers, est["id"], email=email).json()
    headers = login(client, email, "segredo123")

    assert client.delete(f"{API}/{est['id']}/users/{user['id']}", headers=auth_headers).status_code == 204
    assert client.get(f"{API}/{est['id']}/products", headers=headers).status_code == 403


def test_store_admin_cannot_reset_password_of_someone_from_other_stores(client, auth_headers):
    est = establishment(client, auth_headers, STORE)
    email = _email()
    _add(client, auth_headers, est["id"], email=email, role="ADMIN")
    store_admin = login(client, email, "segredo123")
    # A cozinha demo trabalha nas tres lojas; este admin so administra uma
    kitchen = next(u for u in client.get(f"{API}/{est['id']}/users", headers=store_admin).json() if u["email"] == "cozinha@comandahub.local")

    response = client.patch(f"{API}/{est['id']}/users/{kitchen['id']}", headers=store_admin, json={"password": "invadida1"})

    assert response.status_code == 403
    # Mas pode ajustar o perfil dentro da propria loja
    assert client.patch(f"{API}/{est['id']}/users/{kitchen['id']}", headers=store_admin, json={"role": "KITCHEN"}).status_code == 200


def test_user_changes_own_password(client, auth_headers):
    est = establishment(client, auth_headers, STORE)
    email = _email()
    _add(client, auth_headers, est["id"], email=email)
    headers = login(client, email, "segredo123")

    wrong = client.post("/api/v1/auth/me/password", headers=headers, json={"current_password": "errada", "new_password": "nova-senha-2"})
    right = client.post("/api/v1/auth/me/password", headers=headers, json={"current_password": "segredo123", "new_password": "nova-senha-2"})

    assert wrong.status_code == 422
    assert right.status_code == 204
    login(client, email, "nova-senha-2")


def test_login_is_blocked_after_repeated_failures(client, auth_headers):
    est = establishment(client, auth_headers, STORE)
    email = _email()
    _add(client, auth_headers, est["id"], email=email)

    codes = [client.post("/api/v1/auth/login", json={"email": email, "password": "errada"}).status_code for _ in range(5)]
    blocked = client.post("/api/v1/auth/login", json={"email": email, "password": "segredo123"})

    assert codes == [401] * 5
    assert blocked.status_code == 429
    # Outra conta do mesmo IP continua entrando
    assert client.post("/api/v1/auth/login", json={"email": "admin@comandahub.local", "password": "demo123"}).status_code == 200
