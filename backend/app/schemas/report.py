from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel


class ReportOverview(BaseModel):
    total_sold: float
    order_count: int
    average_ticket: float
    canceled_count: int
    in_progress_count: int
    finished_count: int


class SalesByChannel(BaseModel):
    source: str
    total: float
    orders: int


class TopProduct(BaseModel):
    product_name: str
    quantity: int
    total: float


class ProfitByChannel(BaseModel):
    channel: str
    orders: int
    revenue: Decimal
    commission_rate: Decimal
    commission: Decimal
    ingredient_cost: Decimal
    profit: Decimal
    margin: Decimal
