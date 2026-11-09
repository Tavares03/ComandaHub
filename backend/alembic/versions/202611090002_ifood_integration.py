"""Integracao iFood: loja vinculada (merchantId) e dados do pedido do marketplace.

Revision ID: 202611090002
Revises: 202611090001
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "202611090002"
down_revision = "202611090001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("establishments") as batch:
        batch.add_column(sa.Column("ifood_merchant_id", sa.String(length=64), nullable=True))
    op.create_index("ix_establishments_ifood_merchant_id", "establishments", ["ifood_merchant_id"], unique=True)
    with op.batch_alter_table("orders") as batch:
        batch.add_column(sa.Column("integration", sa.String(length=20), nullable=True))
        batch.add_column(sa.Column("external_display_id", sa.String(length=40), nullable=True))
        batch.add_column(sa.Column("marketplace_delivery", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    with op.batch_alter_table("orders") as batch:
        batch.drop_column("marketplace_delivery")
        batch.drop_column("external_display_id")
        batch.drop_column("integration")
    op.drop_index("ix_establishments_ifood_merchant_id", table_name="establishments")
    with op.batch_alter_table("establishments") as batch:
        batch.drop_column("ifood_merchant_id")
