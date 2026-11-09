"""Clientes, cupons e programa de fidelidade.

Revision ID: 202611080005
Revises: 202611080004
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "202611080005"
down_revision = "202611080004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "customers",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("establishment_id", sa.String(length=36), sa.ForeignKey("establishments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(length=140), nullable=False),
        sa.Column("phone", sa.String(length=20), nullable=False),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("neighborhood", sa.String(length=120), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("loyalty_points", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("establishment_id", "phone", name="uq_customer_establishment_phone"),
    )
    op.create_index("ix_customers_establishment_id", "customers", ["establishment_id"])
    op.create_index("ix_customers_phone", "customers", ["phone"])

    op.create_table(
        "coupons",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("establishment_id", sa.String(length=36), sa.ForeignKey("establishments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("code", sa.String(length=40), nullable=False),
        sa.Column("kind", sa.String(length=10), nullable=False),
        sa.Column("value", sa.Numeric(10, 2), nullable=False),
        sa.Column("min_order", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("max_uses", sa.Integer(), nullable=True),
        sa.Column("uses", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("valid_until", sa.Date(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("establishment_id", "code", name="uq_coupon_establishment_code"),
    )
    op.create_index("ix_coupons_establishment_id", "coupons", ["establishment_id"])

    with op.batch_alter_table("orders") as batch:
        batch.add_column(sa.Column("customer_id", sa.String(length=36), nullable=True))
        batch.add_column(sa.Column("coupon_code", sa.String(length=40), nullable=True))
        batch.add_column(sa.Column("loyalty_points_delta", sa.Integer(), nullable=False, server_default="0"))
        batch.create_foreign_key("fk_orders_customer", "customers", ["customer_id"], ["id"], ondelete="SET NULL")
        batch.create_index("ix_orders_customer_id", ["customer_id"])

    with op.batch_alter_table("establishments") as batch:
        batch.add_column(sa.Column("loyalty_enabled", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch.add_column(sa.Column("loyalty_goal", sa.Integer(), nullable=False, server_default="10"))
        batch.add_column(sa.Column("loyalty_reward", sa.Numeric(10, 2), nullable=False, server_default="15"))


def downgrade() -> None:
    with op.batch_alter_table("establishments") as batch:
        batch.drop_column("loyalty_reward")
        batch.drop_column("loyalty_goal")
        batch.drop_column("loyalty_enabled")
    with op.batch_alter_table("orders") as batch:
        batch.drop_index("ix_orders_customer_id")
        batch.drop_constraint("fk_orders_customer", type_="foreignkey")
        batch.drop_column("loyalty_points_delta")
        batch.drop_column("coupon_code")
        batch.drop_column("customer_id")
    op.drop_index("ix_coupons_establishment_id", table_name="coupons")
    op.drop_table("coupons")
    op.drop_index("ix_customers_phone", table_name="customers")
    op.drop_index("ix_customers_establishment_id", table_name="customers")
    op.drop_table("customers")
