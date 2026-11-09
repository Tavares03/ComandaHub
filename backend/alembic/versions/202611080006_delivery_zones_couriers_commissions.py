"""Bairros com taxa de entrega, motoboys e comissao por canal.

Revision ID: 202611080006
Revises: 202611080005
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "202611080006"
down_revision = "202611080005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "delivery_zones",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("establishment_id", sa.String(length=36), sa.ForeignKey("establishments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("fee", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("estimated_minutes", sa.Integer(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.UniqueConstraint("establishment_id", "name", name="uq_delivery_zone_establishment_name"),
    )
    op.create_index("ix_delivery_zones_establishment_id", "delivery_zones", ["establishment_id"])
    op.create_table(
        "couriers",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("establishment_id", sa.String(length=36), sa.ForeignKey("establishments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("phone", sa.String(length=40), nullable=True),
        sa.Column("fee_per_delivery", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_index("ix_couriers_establishment_id", "couriers", ["establishment_id"])
    with op.batch_alter_table("orders") as batch:
        batch.add_column(sa.Column("delivery_zone_id", sa.String(length=36), nullable=True))
        batch.add_column(sa.Column("neighborhood", sa.String(length=120), nullable=True))
        batch.add_column(sa.Column("courier_id", sa.String(length=36), nullable=True))
        batch.create_foreign_key("fk_orders_delivery_zone", "delivery_zones", ["delivery_zone_id"], ["id"], ondelete="SET NULL")
        batch.create_foreign_key("fk_orders_courier", "couriers", ["courier_id"], ["id"], ondelete="SET NULL")
        batch.create_index("ix_orders_courier_id", ["courier_id"])
    with op.batch_alter_table("establishments") as batch:
        batch.add_column(sa.Column("channel_commissions", sa.JSON(), nullable=False, server_default="{}"))


def downgrade() -> None:
    with op.batch_alter_table("establishments") as batch:
        batch.drop_column("channel_commissions")
    with op.batch_alter_table("orders") as batch:
        batch.drop_index("ix_orders_courier_id")
        batch.drop_constraint("fk_orders_courier", type_="foreignkey")
        batch.drop_constraint("fk_orders_delivery_zone", type_="foreignkey")
        batch.drop_column("courier_id")
        batch.drop_column("neighborhood")
        batch.drop_column("delivery_zone_id")
    op.drop_index("ix_couriers_establishment_id", table_name="couriers")
    op.drop_table("couriers")
    op.drop_index("ix_delivery_zones_establishment_id", table_name="delivery_zones")
    op.drop_table("delivery_zones")
