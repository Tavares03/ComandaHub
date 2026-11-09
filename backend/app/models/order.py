from __future__ import annotations

from decimal import Decimal
from enum import Enum

from datetime import datetime

from sqlalchemy import Enum as SAEnum, ForeignKey, Index, Integer, JSON, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, IdMixin, TimestampMixin, UTCDateTime


class OrderSource(str, Enum):
    IFOOD = "IFOOD"
    NINETY_NINE_FOOD = "NINETY_NINE_FOOD"
    OWN_DELIVERY = "OWN_DELIVERY"
    COUNTER = "COUNTER"
    STORE_PICKUP = "STORE_PICKUP"


class FulfillmentType(str, Enum):
    DELIVERY = "DELIVERY"
    PICKUP = "PICKUP"
    COUNTER = "COUNTER"


class PaymentMethod(str, Enum):
    CASH = "CASH"
    CARD = "CARD"
    PIX = "PIX"
    ONLINE = "ONLINE"


class PaymentStatus(str, Enum):
    PENDING = "PENDING"
    PAID = "PAID"
    FAILED = "FAILED"
    REFUNDED = "REFUNDED"


class OrderStatus(str, Enum):
    NEW = "NEW"
    ACCEPTED = "ACCEPTED"
    PREPARING = "PREPARING"
    READY = "READY"
    OUT_FOR_DELIVERY = "OUT_FOR_DELIVERY"
    FINISHED = "FINISHED"
    CANCELED = "CANCELED"


class Order(Base, IdMixin, TimestampMixin):
    __tablename__ = "orders"
    __table_args__ = (
        UniqueConstraint("establishment_id", "source", "external_order_id", name="uq_order_external_source"),
        UniqueConstraint("establishment_id", "order_number", name="uq_order_establishment_number"),
        Index("ix_orders_establishment_status", "establishment_id", "status"),
        Index("ix_orders_establishment_created_at", "establishment_id", "created_at"),
    )

    establishment_id: Mapped[str] = mapped_column(ForeignKey("establishments.id", ondelete="CASCADE"), index=True)
    external_order_id: Mapped[str | None] = mapped_column(String(140), nullable=True)
    source: Mapped[OrderSource] = mapped_column(SAEnum(OrderSource, native_enum=False), index=True)
    order_number: Mapped[str] = mapped_column(String(40), index=True)
    customer_name: Mapped[str | None] = mapped_column(String(140), nullable=True)
    customer_phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    delivery_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    fulfillment_type: Mapped[FulfillmentType] = mapped_column(SAEnum(FulfillmentType, native_enum=False))
    payment_method: Mapped[PaymentMethod] = mapped_column(SAEnum(PaymentMethod, native_enum=False))
    payment_status: Mapped[PaymentStatus] = mapped_column(SAEnum(PaymentStatus, native_enum=False), default=PaymentStatus.PENDING)
    status: Mapped[OrderStatus] = mapped_column(SAEnum(OrderStatus, native_enum=False), default=OrderStatus.NEW, index=True)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"))
    discount: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"))
    delivery_fee: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"))
    total: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"))
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    customer_id: Mapped[str | None] = mapped_column(ForeignKey("customers.id", ondelete="SET NULL"), nullable=True, index=True)
    coupon_code: Mapped[str | None] = mapped_column(String(40), nullable=True)
    # Pontos de fidelidade que o pedido mexeu: +1 ganhou, -meta usou a recompensa (desfeito ao cancelar)
    loyalty_points_delta: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    delivery_zone_id: Mapped[str | None] = mapped_column(ForeignKey("delivery_zones.id", ondelete="SET NULL"), nullable=True)
    neighborhood: Mapped[str | None] = mapped_column(String(120), nullable=True)
    courier_id: Mapped[str | None] = mapped_column(ForeignKey("couriers.id", ondelete="SET NULL"), nullable=True, index=True)
    # Codigo para o cliente acompanhar o pedido do cardapio online (sem login)
    public_token: Mapped[str | None] = mapped_column(String(40), unique=True, nullable=True, index=True)

    establishment = relationship("Establishment", back_populates="orders")
    courier = relationship("Courier")

    @property
    def courier_name(self) -> str | None:
        return self.courier.name if self.courier else None
    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")
    events = relationship("OrderEvent", back_populates="order", cascade="all, delete-orphan", order_by="OrderEvent.created_at")


class OrderItem(Base, IdMixin):
    __tablename__ = "order_items"

    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[str | None] = mapped_column(ForeignKey("products.id", ondelete="SET NULL"), nullable=True)
    product_name: Mapped[str] = mapped_column(String(140))
    quantity: Mapped[int]
    unit_price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    total: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    selected_options: Mapped[list[dict]] = mapped_column(JSON, default=list)
    # Custo dos ingredientes de uma unidade no momento do pedido (para margem e lucro)
    unit_cost: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)

    order = relationship("Order", back_populates="items")


class OrderEvent(Base, IdMixin):
    __tablename__ = "order_events"
    __table_args__ = (Index("ix_order_events_order_created_at", "order_id", "created_at"),)

    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), index=True)
    event_type: Mapped[str] = mapped_column(String(80), index=True)
    previous_status: Mapped[OrderStatus | None] = mapped_column(SAEnum(OrderStatus, native_enum=False), nullable=True)
    new_status: Mapped[OrderStatus | None] = mapped_column(SAEnum(OrderStatus, native_enum=False), nullable=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)

    order = relationship("Order", back_populates="events")
