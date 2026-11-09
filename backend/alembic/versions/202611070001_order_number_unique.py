"""Numero de pedido unico por estabelecimento.

Revision ID: 202611070001
Revises: 202410160001
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "202611070001"
down_revision = "202410160001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    # Renomeia eventuais duplicados antigos (o gerador anterior podia repetir numeros) antes de criar a restricao.
    rows = bind.execute(
        sa.text(
            "SELECT id, establishment_id, order_number FROM orders "
            "WHERE (establishment_id, order_number) IN ("
            "  SELECT establishment_id, order_number FROM orders GROUP BY establishment_id, order_number HAVING COUNT(*) > 1"
            ") ORDER BY establishment_id, order_number, created_at"
        )
    ).fetchall()
    seen: dict[tuple[str, str], int] = {}
    for order_id, establishment_id, order_number in rows:
        key = (establishment_id, order_number)
        seen[key] = seen.get(key, 0) + 1
        if seen[key] > 1:
            bind.execute(
                sa.text("UPDATE orders SET order_number = :number WHERE id = :id"),
                {"number": f"{order_number}-D{seen[key] - 1}", "id": order_id},
            )
    with op.batch_alter_table("orders") as batch:
        batch.create_unique_constraint("uq_order_establishment_number", ["establishment_id", "order_number"])


def downgrade() -> None:
    with op.batch_alter_table("orders") as batch:
        batch.drop_constraint("uq_order_establishment_number", type_="unique")
