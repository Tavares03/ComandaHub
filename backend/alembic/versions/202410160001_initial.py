from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "202410160001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "establishments",
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("legal_name", sa.String(length=160), nullable=True),
        sa.Column("tax_id", sa.String(length=32), nullable=True),
        sa.Column("phone", sa.String(length=40), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("opening_hours", sa.String(length=120), nullable=True),
        sa.Column("logo_url", sa.String(length=500), nullable=True),
        sa.Column("timezone", sa.String(length=80), nullable=False),
        sa.Column("preparation_time", sa.Integer(), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_establishments_name"), "establishments", ["name"], unique=True)

    op.create_table(
        "users",
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)

    op.create_table(
        "categories",
        sa.Column("establishment_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.ForeignKeyConstraint(["establishment_id"], ["establishments.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("establishment_id", "name", name="uq_category_establishment_name"),
    )
    op.create_index(op.f("ix_categories_establishment_id"), "categories", ["establishment_id"], unique=False)

    op.create_table(
        "establishment_memberships",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("establishment_id", sa.String(length=36), nullable=False),
        sa.Column("role", sa.Enum("ADMIN", "ATTENDANT", "KITCHEN", native_enum=False), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.ForeignKeyConstraint(["establishment_id"], ["establishments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "establishment_id", name="uq_membership_user_establishment"),
    )
    op.create_index(op.f("ix_establishment_memberships_establishment_id"), "establishment_memberships", ["establishment_id"], unique=False)
    op.create_index(op.f("ix_establishment_memberships_user_id"), "establishment_memberships", ["user_id"], unique=False)

    op.create_table(
        "products",
        sa.Column("establishment_id", sa.String(length=36), nullable=False),
        sa.Column("category_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=140), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("price", sa.Numeric(10, 2), nullable=False),
        sa.Column("image_url", sa.String(length=500), nullable=True),
        sa.Column("is_available", sa.Boolean(), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["category_id"], ["categories.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["establishment_id"], ["establishments.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("establishment_id", "name", name="uq_product_establishment_name"),
    )
    op.create_index(op.f("ix_products_category_id"), "products", ["category_id"], unique=False)
    op.create_index(op.f("ix_products_establishment_id"), "products", ["establishment_id"], unique=False)
    op.create_index(op.f("ix_products_is_available"), "products", ["is_available"], unique=False)

    op.create_table(
        "orders",
        sa.Column("establishment_id", sa.String(length=36), nullable=False),
        sa.Column("external_order_id", sa.String(length=140), nullable=True),
        sa.Column("source", sa.Enum("IFOOD", "NINETY_NINE_FOOD", "OWN_DELIVERY", "COUNTER", "STORE_PICKUP", native_enum=False), nullable=False),
        sa.Column("order_number", sa.String(length=40), nullable=False),
        sa.Column("customer_name", sa.String(length=140), nullable=True),
        sa.Column("customer_phone", sa.String(length=40), nullable=True),
        sa.Column("delivery_address", sa.Text(), nullable=True),
        sa.Column("fulfillment_type", sa.Enum("DELIVERY", "PICKUP", "COUNTER", native_enum=False), nullable=False),
        sa.Column("payment_method", sa.Enum("CASH", "CARD", "PIX", "ONLINE", native_enum=False), nullable=False),
        sa.Column("payment_status", sa.Enum("PENDING", "PAID", "FAILED", "REFUNDED", native_enum=False), nullable=False),
        sa.Column("status", sa.Enum("NEW", "ACCEPTED", "PREPARING", "READY", "OUT_FOR_DELIVERY", "FINISHED", "CANCELED", native_enum=False), nullable=False),
        sa.Column("subtotal", sa.Numeric(10, 2), nullable=False),
        sa.Column("discount", sa.Numeric(10, 2), nullable=False),
        sa.Column("delivery_fee", sa.Numeric(10, 2), nullable=False),
        sa.Column("total", sa.Numeric(10, 2), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["establishment_id"], ["establishments.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("establishment_id", "source", "external_order_id", name="uq_order_external_source"),
    )
    op.create_index("ix_orders_establishment_created_at", "orders", ["establishment_id", "created_at"], unique=False)
    op.create_index("ix_orders_establishment_status", "orders", ["establishment_id", "status"], unique=False)
    op.create_index(op.f("ix_orders_establishment_id"), "orders", ["establishment_id"], unique=False)
    op.create_index(op.f("ix_orders_order_number"), "orders", ["order_number"], unique=False)
    op.create_index(op.f("ix_orders_source"), "orders", ["source"], unique=False)
    op.create_index(op.f("ix_orders_status"), "orders", ["status"], unique=False)

    op.create_table(
        "product_option_groups",
        sa.Column("product_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("min_choices", sa.Integer(), nullable=False),
        sa.Column("max_choices", sa.Integer(), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_product_option_groups_product_id"), "product_option_groups", ["product_id"], unique=False)

    op.create_table(
        "order_events",
        sa.Column("order_id", sa.String(length=36), nullable=False),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("previous_status", sa.Enum("NEW", "ACCEPTED", "PREPARING", "READY", "OUT_FOR_DELIVERY", "FINISHED", "CANCELED", native_enum=False), nullable=True),
        sa.Column("new_status", sa.Enum("NEW", "ACCEPTED", "PREPARING", "READY", "OUT_FOR_DELIVERY", "FINISHED", "CANCELED", native_enum=False), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_order_events_order_created_at", "order_events", ["order_id", "created_at"], unique=False)
    op.create_index(op.f("ix_order_events_event_type"), "order_events", ["event_type"], unique=False)
    op.create_index(op.f("ix_order_events_order_id"), "order_events", ["order_id"], unique=False)

    op.create_table(
        "order_items",
        sa.Column("order_id", sa.String(length=36), nullable=False),
        sa.Column("product_id", sa.String(length=36), nullable=True),
        sa.Column("product_name", sa.String(length=140), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_price", sa.Numeric(10, 2), nullable=False),
        sa.Column("total", sa.Numeric(10, 2), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("selected_options", sa.JSON(), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_order_items_order_id"), "order_items", ["order_id"], unique=False)

    op.create_table(
        "product_options",
        sa.Column("group_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("price_delta", sa.Numeric(10, 2), nullable=False),
        sa.Column("is_available", sa.Boolean(), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.ForeignKeyConstraint(["group_id"], ["product_option_groups.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_product_options_group_id"), "product_options", ["group_id"], unique=False)


def downgrade() -> None:
    op.drop_table("product_options")
    op.drop_table("order_items")
    op.drop_table("order_events")
    op.drop_table("product_option_groups")
    op.drop_table("orders")
    op.drop_table("products")
    op.drop_table("establishment_memberships")
    op.drop_table("categories")
    op.drop_table("users")
    op.drop_table("establishments")
