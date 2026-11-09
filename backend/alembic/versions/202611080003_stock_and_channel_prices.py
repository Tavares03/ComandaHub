"""Estoque por ingrediente (ficha tecnica, custo, historico) e preco por canal.

Revision ID: 202611080003
Revises: 202611080002
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "202611080003"
down_revision = "202611080002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("ingredients") as batch:
        batch.add_column(sa.Column("unit", sa.String(length=8), nullable=False, server_default="un"))
        batch.add_column(sa.Column("stock_quantity", sa.Numeric(12, 3), nullable=True))
        batch.add_column(sa.Column("min_stock", sa.Numeric(12, 3), nullable=True))
        batch.add_column(sa.Column("cost_per_unit", sa.Numeric(10, 4), nullable=False, server_default="0"))
        batch.add_column(sa.Column("auto_paused_channels", sa.JSON(), nullable=False, server_default="[]"))

    with op.batch_alter_table("product_ingredients") as batch:
        batch.add_column(sa.Column("quantity", sa.Numeric(12, 3), nullable=False, server_default="0"))

    with op.batch_alter_table("product_options") as batch:
        batch.add_column(sa.Column("ingredient_quantity", sa.Numeric(12, 3), nullable=False, server_default="0"))

    with op.batch_alter_table("products") as batch:
        batch.add_column(sa.Column("channel_prices", sa.JSON(), nullable=False, server_default="{}"))

    with op.batch_alter_table("order_items") as batch:
        batch.add_column(sa.Column("unit_cost", sa.Numeric(10, 2), nullable=True))

    op.create_table(
        "stock_movements",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("establishment_id", sa.String(length=36), sa.ForeignKey("establishments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("ingredient_id", sa.String(length=36), sa.ForeignKey("ingredients.id", ondelete="CASCADE"), nullable=False),
        sa.Column("reason", sa.String(length=16), nullable=False),
        sa.Column("delta", sa.Numeric(12, 3), nullable=False),
        sa.Column("balance", sa.Numeric(12, 3), nullable=False),
        sa.Column("order_id", sa.String(length=36), sa.ForeignKey("orders.id", ondelete="SET NULL"), nullable=True),
        sa.Column("unit_cost", sa.Numeric(10, 4), nullable=True),
        sa.Column("note", sa.String(length=200), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_stock_movements_establishment_id", "stock_movements", ["establishment_id"])
    op.create_index("ix_stock_movements_order_id", "stock_movements", ["order_id"])
    op.create_index("ix_stock_movements_ingredient_created", "stock_movements", ["ingredient_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_stock_movements_ingredient_created", table_name="stock_movements")
    op.drop_index("ix_stock_movements_order_id", table_name="stock_movements")
    op.drop_index("ix_stock_movements_establishment_id", table_name="stock_movements")
    op.drop_table("stock_movements")
    with op.batch_alter_table("order_items") as batch:
        batch.drop_column("unit_cost")
    with op.batch_alter_table("products") as batch:
        batch.drop_column("channel_prices")
    with op.batch_alter_table("product_options") as batch:
        batch.drop_column("ingredient_quantity")
    with op.batch_alter_table("product_ingredients") as batch:
        batch.drop_column("quantity")
    with op.batch_alter_table("ingredients") as batch:
        batch.drop_column("auto_paused_channels")
        batch.drop_column("cost_per_unit")
        batch.drop_column("min_stock")
        batch.drop_column("stock_quantity")
        batch.drop_column("unit")
