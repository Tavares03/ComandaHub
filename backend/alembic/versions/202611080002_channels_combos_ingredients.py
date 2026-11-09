"""Pausa por canal (iFood, 99, Local), combo dentro do item e ingredientes.

Revision ID: 202611080002
Revises: 202611080001
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "202611080002"
down_revision = "202611080001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ingredients",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("establishment_id", sa.String(length=36), sa.ForeignKey("establishments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.UniqueConstraint("establishment_id", "name", name="uq_ingredient_establishment_name"),
    )
    op.create_index("ix_ingredients_establishment_id", "ingredients", ["establishment_id"])

    op.create_table(
        "product_ingredients",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("product_id", sa.String(length=36), sa.ForeignKey("products.id", ondelete="CASCADE"), nullable=False),
        sa.Column("ingredient_id", sa.String(length=36), sa.ForeignKey("ingredients.id", ondelete="CASCADE"), nullable=False),
        sa.Column("essential", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("paused_channels", sa.JSON(), nullable=False, server_default="[]"),
        sa.UniqueConstraint("product_id", "ingredient_id", name="uq_product_ingredient"),
    )
    op.create_index("ix_product_ingredients_product_id", "product_ingredients", ["product_id"])
    op.create_index("ix_product_ingredients_ingredient_id", "product_ingredients", ["ingredient_id"])

    with op.batch_alter_table("products") as batch:
        batch.add_column(sa.Column("paused_channels", sa.JSON(), nullable=False, server_default="[]"))

    with op.batch_alter_table("product_option_groups") as batch:
        batch.add_column(sa.Column("depends_on_option_id", sa.String(length=36), nullable=True))

    with op.batch_alter_table("product_options") as batch:
        batch.add_column(sa.Column("paused_channels", sa.JSON(), nullable=False, server_default="[]"))
        batch.add_column(sa.Column("linked_product_id", sa.String(length=36), nullable=True))
        batch.add_column(sa.Column("ingredient_id", sa.String(length=36), nullable=True))
        batch.create_foreign_key("fk_product_options_linked_product", "products", ["linked_product_id"], ["id"], ondelete="SET NULL")
        batch.create_foreign_key("fk_product_options_ingredient", "ingredients", ["ingredient_id"], ["id"], ondelete="SET NULL")
        batch.create_index("ix_product_options_linked_product_id", ["linked_product_id"])
        batch.create_index("ix_product_options_ingredient_id", ["ingredient_id"])


def downgrade() -> None:
    with op.batch_alter_table("product_options") as batch:
        batch.drop_index("ix_product_options_ingredient_id")
        batch.drop_index("ix_product_options_linked_product_id")
        batch.drop_constraint("fk_product_options_ingredient", type_="foreignkey")
        batch.drop_constraint("fk_product_options_linked_product", type_="foreignkey")
        batch.drop_column("ingredient_id")
        batch.drop_column("linked_product_id")
        batch.drop_column("paused_channels")
    with op.batch_alter_table("product_option_groups") as batch:
        batch.drop_column("depends_on_option_id")
    with op.batch_alter_table("products") as batch:
        batch.drop_column("paused_channels")
    op.drop_index("ix_product_ingredients_ingredient_id", table_name="product_ingredients")
    op.drop_index("ix_product_ingredients_product_id", table_name="product_ingredients")
    op.drop_table("product_ingredients")
    op.drop_index("ix_ingredients_establishment_id", table_name="ingredients")
    op.drop_table("ingredients")
