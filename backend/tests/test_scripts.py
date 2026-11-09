"""Scripts de operacao: seed demo bloqueado em producao e criacao do primeiro administrador."""
from __future__ import annotations

import sys
from types import SimpleNamespace
from uuid import uuid4

import pytest

import scripts.create_admin as create_admin
import scripts.seed as seed
from tests.helpers import login


def test_demo_seed_refuses_to_run_in_production(monkeypatch):
    monkeypatch.setattr(seed, "get_settings", lambda: SimpleNamespace(is_production=True))

    with pytest.raises(SystemExit):
        seed.main()


def test_create_admin_creates_store_and_admin_that_can_log_in(client, monkeypatch):
    email = f"dono-{uuid4().hex[:6]}@minhaloja.com.br"
    store = f"Loja Nova {uuid4().hex[:4]}"
    monkeypatch.setattr(sys, "argv", ["create_admin", "--email", email, "--name", "Dona", "--store", store, "--password", "senha-forte-1"])

    create_admin.main()

    me = client.get("/api/v1/auth/me", headers=login(client, email, "senha-forte-1")).json()
    assert [(e["name"], e["role"]) for e in me["establishments"]] == [(store, "ADMIN")]
