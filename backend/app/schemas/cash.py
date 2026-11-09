from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, Field

from app.models.order import PaymentMethod

Money = Annotated[Decimal, Field(ge=0, max_digits=10, decimal_places=2)]


class CashOpen(BaseModel):
    opening_amount: Money = Decimal("0.00")
    notes: str | None = Field(default=None, max_length=500)


class CashMovementCreate(BaseModel):
    kind: Literal["WITHDRAWAL", "SUPPLY"]
    amount: Annotated[Decimal, Field(gt=0, max_digits=10, decimal_places=2)]
    note: str | None = Field(default=None, max_length=200)


class CashClose(BaseModel):
    counted_amount: Money
    notes: str | None = Field(default=None, max_length=500)


class CashMovementOut(BaseModel):
    id: str
    kind: str
    amount: Decimal
    note: str | None = None
    user_name: str | None = None
    created_at: datetime


class SalesByMethod(BaseModel):
    payment_method: PaymentMethod
    orders: int
    total: Decimal


class CashSummary(BaseModel):
    id: str
    opened_at: datetime
    opened_by_name: str | None = None
    opening_amount: Decimal
    closed_at: datetime | None = None
    closed_by_name: str | None = None
    counted_amount: Decimal | None = None
    notes: str | None = None
    order_count: int
    canceled_count: int
    total_sales: Decimal
    sales_by_method: list[SalesByMethod]
    withdrawals: Decimal
    supplies: Decimal
    # Troco + vendas em dinheiro + reforcos - sangrias
    expected_cash: Decimal
    # Contado - esperado (negativo = faltou dinheiro)
    difference: Decimal | None = None
    movements: list[CashMovementOut]
