"""Caixa: turnos (abertura/fechamento) e sangrias/reforcos.

Revision ID: 202611080004
Revises: 202611080003
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "202611080004"
down_revision = "202611080003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "cash_sessions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("establishment_id", sa.String(length=36), sa.ForeignKey("establishments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("opened_by_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("opening_amount", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_by_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("counted_amount", sa.Numeric(10, 2), nullable=True),
        sa.Column("expected_cash", sa.Numeric(10, 2), nullable=True),
        sa.Column("total_sales", sa.Numeric(10, 2), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
    )
    op.create_index("ix_cash_sessions_establishment_id", "cash_sessions", ["establishment_id"])
    op.create_index("ix_cash_sessions_establishment_opened", "cash_sessions", ["establishment_id", "opened_at"])
    op.create_table(
        "cash_movements",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("session_id", sa.String(length=36), sa.ForeignKey("cash_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("note", sa.String(length=200), nullable=True),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_cash_movements_session_id", "cash_movements", ["session_id"])


def downgrade() -> None:
    op.drop_index("ix_cash_movements_session_id", table_name="cash_movements")
    op.drop_table("cash_movements")
    op.drop_index("ix_cash_sessions_establishment_opened", table_name="cash_sessions")
    op.drop_index("ix_cash_sessions_establishment_id", table_name="cash_sessions")
    op.drop_table("cash_sessions")
