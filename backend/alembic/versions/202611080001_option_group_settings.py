"""Personalizacao de itens: ordem, regra de preco e repeticao nos grupos de opcoes.

Revision ID: 202611080001
Revises: 202611070001
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "202611080001"
down_revision = "202611070001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("product_option_groups") as batch:
        batch.add_column(sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"))
        batch.add_column(sa.Column("pricing_mode", sa.String(length=16), nullable=False, server_default="SUM"))
        batch.add_column(sa.Column("allow_repeat", sa.Boolean(), nullable=False, server_default=sa.false()))
    with op.batch_alter_table("product_options") as batch:
        batch.add_column(sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"))


def downgrade() -> None:
    with op.batch_alter_table("product_options") as batch:
        batch.drop_column("sort_order")
    with op.batch_alter_table("product_option_groups") as batch:
        batch.drop_column("allow_repeat")
        batch.drop_column("pricing_mode")
        batch.drop_column("sort_order")
