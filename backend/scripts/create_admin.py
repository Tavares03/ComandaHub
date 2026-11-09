"""Cria o primeiro administrador (e a loja) em um banco novo, sem dados demo.

Uso:
    python -m scripts.create_admin --email dono@minhaloja.com.br --name "Maria" --store "Minha Hamburgueria"

A senha e pedida no terminal (ou passe --password). Rodar de novo com o mesmo e-mail so adiciona o
acesso a loja informada; use --reset-password para trocar a senha de um usuario existente.
"""
from __future__ import annotations

import argparse
import getpass
import re
import unicodedata

from sqlalchemy import func, select

import app.db as db_module
from app.core.security import hash_password
from app.models.establishment import Establishment
from app.models.user import EstablishmentMembership, User, UserRole

MIN_PASSWORD = 8


def slugify(name: str) -> str:
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", ascii_name.lower()).strip("-") or "loja"


def unique_slug(db, name: str) -> str:
    base = slugify(name)
    slug, counter = base, 2
    while db.scalar(select(Establishment.id).where(Establishment.slug == slug)):
        slug, counter = f"{base}-{counter}", counter + 1
    return slug


def ask_password() -> str:
    while True:
        password = getpass.getpass(f"Senha (minimo {MIN_PASSWORD} caracteres): ")
        if len(password) < MIN_PASSWORD:
            print("Senha curta demais.")
            continue
        if password != getpass.getpass("Repita a senha: "):
            print("As senhas nao conferem.")
            continue
        return password


def main() -> None:
    parser = argparse.ArgumentParser(description="Cria o administrador e a loja iniciais do ComandaHub.")
    parser.add_argument("--email", required=True)
    parser.add_argument("--name", default="Administrador")
    parser.add_argument("--store", required=True, help="Nome da loja (criada se ainda nao existir)")
    parser.add_argument("--password", help="Evite em producao: fica no historico do terminal")
    parser.add_argument("--reset-password", action="store_true", help="Troca a senha se o usuario ja existir")
    args = parser.parse_args()

    email = args.email.strip().lower()
    with db_module.SessionLocal() as db:
        store = db.scalar(select(Establishment).where(Establishment.name == args.store.strip()))
        if store is None:
            store = Establishment(name=args.store.strip(), slug=unique_slug(db, args.store), channel_commissions={})
            db.add(store)
            db.flush()
            print(f"Loja criada: {store.name} (/cardapio/{store.slug})")

        user = db.scalar(select(User).where(func.lower(User.email) == email))
        if user is None:
            password = args.password or ask_password()
            if len(password) < MIN_PASSWORD:
                raise SystemExit(f"A senha precisa ter pelo menos {MIN_PASSWORD} caracteres.")
            user = User(name=args.name.strip(), email=email, password_hash=hash_password(password), is_active=True)
            db.add(user)
            db.flush()
            print(f"Usuario criado: {email}")
        elif args.reset_password:
            user.password_hash = hash_password(args.password or ask_password())
            print(f"Senha atualizada: {email}")

        membership = db.scalar(
            select(EstablishmentMembership).where(
                EstablishmentMembership.user_id == user.id, EstablishmentMembership.establishment_id == store.id
            )
        )
        if membership is None:
            db.add(EstablishmentMembership(user_id=user.id, establishment_id=store.id, role=UserRole.ADMIN))
        else:
            membership.role = UserRole.ADMIN
        db.commit()
        print(f"{email} e administrador de {store.name}.")


if __name__ == "__main__":
    main()
