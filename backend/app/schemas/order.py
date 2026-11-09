from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, model_validator

from app.models.order import FulfillmentType, OrderSource, OrderStatus, PaymentMethod, PaymentStatus
from app.schemas.common import ORMModel


class OrderItemOptionOut(BaseModel):
    name: str
    price_delta: Decimal


class OrderItemOut(ORMModel):
    unit_cost: Decimal | None = None
    id: str
    product_id: str | None = None
    product_name: str
    quantity: int
    unit_price: Decimal
    total: Decimal
    notes: str | None = None
    selected_options: list[dict] = []


class OrderEventOut(ORMModel):
    id: str
    event_type: str
    previous_status: OrderStatus | None = None
    new_status: OrderStatus | None = None
    payload: dict = {}
    created_at: datetime


class OrderOut(ORMModel):
    id: str
    establishment_id: str
    external_order_id: str | None = None
    source: OrderSource
    order_number: str
    customer_name: str | None = None
    customer_phone: str | None = None
    delivery_address: str | None = None
    fulfillment_type: FulfillmentType
    payment_method: PaymentMethod
    payment_status: PaymentStatus
    status: OrderStatus
    subtotal: Decimal
    discount: Decimal
    delivery_fee: Decimal
    total: Decimal
    notes: str | None = None
    customer_id: str | None = None
    coupon_code: str | None = None
    delivery_zone_id: str | None = None
    neighborhood: str | None = None
    courier_id: str | None = None
    courier_name: str | None = None
    integration: str | None = None
    external_display_id: str | None = None
    marketplace_delivery: bool = False
    created_at: datetime
    updated_at: datetime
    items: list[OrderItemOut] = []
    events: list[OrderEventOut] = []


class OrderItemOptionCreate(BaseModel):
    option_id: str
    quantity: int = Field(default=1, ge=1, le=20)
    # Observacao de uma escolha especifica (ex.: sabor Calabresa "sem cebola")
    notes: str | None = Field(default=None, max_length=120)


class OrderItemCreate(BaseModel):
    product_id: str
    quantity: int = Field(ge=1, le=99)
    options: list[OrderItemOptionCreate] = Field(default_factory=list, max_length=40)
    # Formato antigo (cada id = 1 unidade); continua aceito pelos conectores e integracoes.
    option_ids: list[str] = Field(default_factory=list, max_length=20)
    notes: str | None = Field(default=None, max_length=300)

    def all_selections(self) -> list[OrderItemOptionCreate]:
        return [*self.options, *(OrderItemOptionCreate(option_id=option_id) for option_id in self.option_ids)]


class LocalOrderCreate(BaseModel):
    customer_name: str | None = None
    customer_phone: str | None = None
    delivery_address: str | None = None
    fulfillment_type: FulfillmentType
    payment_method: PaymentMethod
    payment_status: PaymentStatus = PaymentStatus.PENDING
    delivery_fee: Decimal = Field(default=Decimal("0.00"), ge=0, max_digits=10, decimal_places=2)
    discount: Decimal = Field(default=Decimal("0.00"), ge=0, max_digits=10, decimal_places=2)
    notes: str | None = Field(default=None, max_length=500)
    items: list[OrderItemCreate] = Field(min_length=1, max_length=50)
    coupon_code: str | None = Field(default=None, max_length=40)
    # Usa a recompensa do programa de fidelidade do cliente (precisa de telefone)
    use_loyalty_reward: bool = False
    # Bairro do delivery: define a taxa (a menos que delivery_fee venha preenchida)
    delivery_zone_id: str | None = None

    @model_validator(mode="after")
    def validate_delivery_fields(self) -> "LocalOrderCreate":
        if self.fulfillment_type == FulfillmentType.DELIVERY and not self.delivery_address:
            raise ValueError("Endereco obrigatorio para delivery proprio")
        if self.fulfillment_type != FulfillmentType.DELIVERY:
            self.delivery_fee = Decimal("0.00")
        return self


class OrderStatusUpdate(BaseModel):
    status: OrderStatus
    cancel_reason: str | None = None
    # Pedido do iFood: codigo do motivo oficial (GET .../ifood/cancellation-reasons)
    cancel_code: str | None = Field(default=None, max_length=10)
    # Motoboy que levou o pedido (ao mudar para "saiu para entrega")
    courier_id: str | None = None


class OrderCourierUpdate(BaseModel):
    courier_id: str | None = None


class OrderPaymentUpdate(BaseModel):
    payment_status: PaymentStatus


class PendingCount(BaseModel):
    new_orders: int


class OrderListResponse(BaseModel):
    items: list[OrderOut]
    total: int
    limit: int
    offset: int
