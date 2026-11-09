from __future__ import annotations

from decimal import Decimal

from sqlalchemy import Boolean, ForeignKey, Integer, Numeric, String, UniqueConstraint, true
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, IdMixin


class DeliveryZone(Base, IdMixin):
    """Bairro (ou regiao) atendido no delivery proprio, com a taxa de entrega."""

    __tablename__ = "delivery_zones"
    __table_args__ = (UniqueConstraint("establishment_id", "name", name="uq_delivery_zone_establishment_name"),)

    establishment_id: Mapped[str] = mapped_column(ForeignKey("establishments.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    fee: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"))
    estimated_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())


class Courier(Base, IdMixin):
    """Motoboy. fee_per_delivery: quanto ele recebe por entrega (0 = recebe a taxa cobrada)."""

    __tablename__ = "couriers"

    establishment_id: Mapped[str] = mapped_column(ForeignKey("establishments.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    fee_per_delivery: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"), server_default="0")
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())
