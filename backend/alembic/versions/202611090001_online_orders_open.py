"""Cardapio online: chave "recebendo pedidos agora" (loja aberta/fechada).

Revision ID: 202611090001
Revises: 202611080007
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "202611090001"
down_revision = "202611080007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("establishments") as batch:
        batch.add_column(sa.Column("online_orders_open", sa.Boolean(), nullable=False, server_default=sa.true()))


def downgrade() -> None:
    with op.batch_alter_table("establishments") as batch:
        batch.drop_column("online_orders_open")
