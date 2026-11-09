from __future__ import annotations

import os
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
os.environ["SECRET_KEY"] = "test-secret-key-with-at-least-32-bytes!!"
# Testes nunca falam com o iFood de verdade (o backend/.env pode ter credenciais reais)
os.environ["IFOOD_CLIENT_ID"] = ""
os.environ["IFOOD_CLIENT_SECRET"] = ""
os.environ["IFOOD_POLLING_ENABLED"] = "false"

from app.core.deps import get_db  # noqa: E402
from app.core.rate_limit import limiter  # noqa: E402
from app.db import get_db as app_get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Base  # noqa: E402
from scripts.seed import main as seed_main  # noqa: E402

engine = create_engine(
    "sqlite+pysqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, class_=Session)


def override_get_db() -> Generator[Session, None, None]:
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="session", autouse=True)
def prepare_database() -> None:
    Base.metadata.create_all(bind=engine)
    import app.db as db_module

    db_module.SessionLocal = TestingSessionLocal
    seed_main()


@pytest.fixture(autouse=True)
def reset_rate_limits() -> Generator[None, None, None]:
    # Todos os testes vem do mesmo "IP": cada teste comeca com os limites zerados
    limiter.reset()
    yield
    limiter.reset()


@pytest.fixture()
def client() -> TestClient:
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[app_get_db] = override_get_db
    return TestClient(app)


@pytest.fixture()
def auth_headers(client: TestClient) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"email": "admin@comandahub.local", "password": "demo123"})
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def kitchen_headers(client: TestClient) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"email": "cozinha@comandahub.local", "password": "demo123"})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture()
def attendant_headers(client: TestClient) -> dict[str, str]:
    # Atendente so do Burger Station
    response = client.post("/api/v1/auth/login", json={"email": "burger@comandahub.local", "password": "demo123"})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}
