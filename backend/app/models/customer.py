from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, true
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, IdMixin, TimestampMixin, UTCDateTime, utcnow


class Customer(Base, IdMixin, TimestampMixin):
    """Cliente da loja, identificado pelo telefone (so digitos)."""

    __tablename__ = "customers"
    __table_args__ = (UniqueConstraint("establishment_id", "phone", name="uq_customer_establishment_phone"),)

    establishment_id: Mapped[str] = mapped_column(ForeignKey("establishments.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(140))
    phone: Mapped[str] = mapped_column(String(20), index=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    neighborhood: Mapped[str | None] = mapped_column(String(120), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Pedidos acumulados no programa de fidelidade (zera ao usar a recompensa)
    loyalty_points: Mapped[int] = mapped_column(Integer, default=0, server_default="0")


class Coupon(Base, IdMixin):
    """Cupom de desconto: PERCENT (% do subtotal) ou FIXED (valor em R$)."""

    __tablename__ = "coupons"
    __table_args__ = (UniqueConstraint("establishment_id", "code", name="uq_coupon_establishment_code"),)

    establishment_id: Mapped[str] = mapped_column(ForeignKey("establishments.id", ondelete="CASCADE"), index=True)
    code: Mapped[str] = mapped_column(String(40))
    kind: Mapped[str] = mapped_column(String(10))
    value: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    min_order: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"), server_default="0")
    # None = sem limite de usos
    max_uses: Mapped[int | None] = mapped_column(Integer, nullable=True)
    uses: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    # Ultimo dia valido (inclusive); None = nao expira
    valid_until: Mapped[date | None] = mapped_column(Date, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, nullable=False)
