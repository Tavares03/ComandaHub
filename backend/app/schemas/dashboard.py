from __future__ import annotations

from app.schemas.order import OrderOut

from pydantic import BaseModel


class MetricCard(BaseModel):
    label: str
    value: float | int | str


class DashboardResponse(BaseModel):
    orders_today: int
    in_progress: int
    finished_today: int
    canceled_today: int
    gross_revenue_today: float
    average_ticket_today: float
    sales_by_channel: list[dict]
    orders_by_hour: list[dict]
    sales_last_7_days: list[dict]
    recent_orders: list[OrderOut]
