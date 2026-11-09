from __future__ import annotations

from decimal import Decimal

from sqlalchemy import JSON, Boolean, Integer, Numeric, String, Text, false, true
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, IdMixin, TimestampMixin


class Establishment(Base, IdMixin, TimestampMixin):
    __tablename__ = "establishments"

    name: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    legal_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    tax_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    opening_hours: Mapped[str | None] = mapped_column(String(120), default="Todos os dias, 18h as 23h")
    logo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    timezone: Mapped[str] = mapped_column(String(80), default="America/Sao_Paulo")
    preparation_time: Mapped[int] = mapped_column(Integer, default=18)
    # Fidelidade: a cada loyalty_goal pedidos, o proximo ganha loyalty_reward de desconto
    loyalty_enabled: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    loyalty_goal: Mapped[int] = mapped_column(Integer, default=10, server_default="10")
    loyalty_reward: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("15.00"), server_default="15")
    # Comissao de cada canal em %, ex.: {"IFOOD": "23", "NINETY_NINE_FOOD": "15", "LOCAL": "0"} (relatorio de lucro)
    channel_commissions: Mapped[dict[str, str]] = mapped_column(JSON, default=dict, server_default="{}")
    # Cardapio online: /cardapio/<slug>. WhatsApp so com digitos (DDD + numero).
    slug: Mapped[str | None] = mapped_column(String(80), unique=True, nullable=True, index=True)
    whatsapp: Mapped[str | None] = mapped_column(String(20), nullable=True)
    online_menu_enabled: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    # Loja aberta/fechada para pedidos online: o cardapio continua visivel, mas nao aceita pedido fechado
    online_orders_open: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())

    memberships = relationship("EstablishmentMembership", back_populates="establishment", cascade="all, delete-orphan")
    categories = relationship("Category", back_populates="establishment", cascade="all, delete-orphan")
    products = relationship("Product", back_populates="establishment", cascade="all, delete-orphan")
    orders = relationship("Order", back_populates="establishment", cascade="all, delete-orphan")
