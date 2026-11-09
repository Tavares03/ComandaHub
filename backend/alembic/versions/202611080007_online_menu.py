"""Cardapio online: endereco publico da loja (slug), WhatsApp e codigo de acompanhamento do pedido.

Revision ID: 202611080007
Revises: 202611080006
"""
from __future__ import annotations

import re
import unicodedata

import sqlalchemy as sa
from alembic import op

revision = "202611080007"
down_revision = "202611080006"
branch_labels = None
depends_on = None


def slugify(name: str) -> str:
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", ascii_name.lower()).strip("-") or "loja"


def upgrade() -> None:
    with op.batch_alter_table("establishments") as batch:
        batch.add_column(sa.Column("slug", sa.String(length=80), nullable=True))
        batch.add_column(sa.Column("whatsapp", sa.String(length=20), nullable=True))
        batch.add_column(sa.Column("online_menu_enabled", sa.Boolean(), nullable=False, server_default=sa.false()))
    with op.batch_alter_table("orders") as batch:
        batch.add_column(sa.Column("public_token", sa.String(length=40), nullable=True))

    # Lojas que ja existem ganham um endereco a partir do nome (Burger Station -> burger-station)
    conn = op.get_bind()
    used: set[str] = set()
    for establishment_id, name in conn.execute(sa.text("SELECT id, name FROM establishments ORDER BY name")).all():
        base = slugify(name)
        slug, counter = base, 2
        while slug in used:
            slug, counter = f"{base}-{counter}", counter + 1
        used.add(slug)
        conn.execute(sa.text("UPDATE establishments SET slug = :slug WHERE id = :id"), {"slug": slug, "id": establishment_id})

    op.create_index("ix_establishments_slug", "establishments", ["slug"], unique=True)
    op.create_index("ix_orders_public_token", "orders", ["public_token"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_orders_public_token", table_name="orders")
    op.drop_index("ix_establishments_slug", table_name="establishments")
    with op.batch_alter_table("orders") as batch:
        batch.drop_column("public_token")
    with op.batch_alter_table("establishments") as batch:
        batch.drop_column("online_menu_enabled")
        batch.drop_column("whatsapp")
        batch.drop_column("slug")
