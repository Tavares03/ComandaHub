from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import ForeignKey, Index, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, IdMixin, UTCDateTime


class CashSession(Base, IdMixin):
    """Um turno de caixa: abre com o troco, fecha com o valor contado na gaveta."""

    __tablename__ = "cash_sessions"
    __table_args__ = (Index("ix_cash_sessions_establishment_opened", "establishment_id", "opened_at"),)

    establishment_id: Mapped[str] = mapped_column(ForeignKey("establishments.id", ondelete="CASCADE"), index=True)
    opened_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    opened_by_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    opening_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"))
    closed_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    closed_by_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    counted_amount: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    # Retrato no fechamento: quanto deveria ter na gaveta e o total vendido no turno
    expected_cash: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    total_sales: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    opened_by = relationship("User", foreign_keys=[opened_by_id])
    closed_by = relationship("User", foreign_keys=[closed_by_id])
    movements = relationship("CashMovement", back_populates="session", cascade="all, delete-orphan", order_by="CashMovement.created_at")


class CashMovement(Base, IdMixin):
    """Sangria (WITHDRAWAL: tirou dinheiro da gaveta) ou reforco (SUPPLY: colocou troco)."""

    __tablename__ = "cash_movements"

    session_id: Mapped[str] = mapped_column(ForeignKey("cash_sessions.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(16))
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    note: Mapped[str | None] = mapped_column(String(200), nullable=True)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)

    session = relationship("CashSession", back_populates="movements")
    user = relationship("User")
