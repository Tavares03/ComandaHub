from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Protocol

from app.models.order import FulfillmentType, OrderSource, PaymentMethod, PaymentStatus


@dataclass(frozen=True)
class NormalizedOrderItem:
    product_id: str
    quantity: int
    option_ids: list[str] = field(default_factory=list)
    notes: str | None = None


@dataclass(frozen=True)
class NormalizedOrder:
    external_order_id: str
    source: OrderSource
    customer_name: str | None
    customer_phone: str | None
    delivery_address: str | None
    fulfillment_type: FulfillmentType
    payment_method: PaymentMethod
    payment_status: PaymentStatus
    delivery_fee: Decimal
    discount: Decimal
    notes: str | None
    items: list[NormalizedOrderItem]
    raw_payload: dict


class BaseOrderConnector(Protocol):
    source: OrderSource

    def receive_orders(self) -> list[NormalizedOrder]:
        ...

    def normalize_order(self, payload: dict) -> NormalizedOrder:
        ...

    def update_status(self, external_order_id: str, status: str) -> None:
        ...

    def process_cancellation(self, external_order_id: str, reason: str) -> None:
        ...
