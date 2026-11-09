"""Espera o banco aceitar conexoes antes das migrations (subida do container).

Em PostgreSQL, se o servidor responde mas o banco ainda nao existe (ex.: Postgres compartilhado
com outros projetos), cria o banco. Uso: python -m scripts.wait_for_db [timeout_em_segundos]
"""
from __future__ import annotations

import re
import sys
import time

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import OperationalError

from app.core.config import get_settings


def create_database_if_missing(url: str) -> bool:
    parsed = make_url(url)
    name = parsed.database or ""
    if not parsed.drivername.startswith("postgresql") or not re.fullmatch(r"[A-Za-z0-9_]+", name):
        return False
    admin = create_engine(parsed.set(database="postgres"), isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as connection:
            if connection.scalar(text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": name}):
                return False
            connection.execute(text(f'CREATE DATABASE "{name}"'))
            print(f"Banco '{name}' criado.")
            return True
    finally:
        admin.dispose()


def main(timeout_seconds: int = 60) -> None:
    url = get_settings().database_url
    engine = create_engine(url, pool_pre_ping=True)
    deadline = time.monotonic() + timeout_seconds
    while True:
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            print("Banco de dados disponivel.")
            return
        except OperationalError as exc:
            if "does not exist" in str(exc.orig) and create_database_if_missing(url):
                continue
            if time.monotonic() > deadline:
                print(f"Banco de dados indisponivel apos {timeout_seconds}s: {exc.orig}", file=sys.stderr)
                raise SystemExit(1) from exc
            print("Aguardando o banco de dados...")
            time.sleep(2)


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 60)
