from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import ORMModel

Money = Annotated[Decimal, Field(ge=0, max_digits=10, decimal_places=2)]


class CustomerOut(BaseModel):
    id: str
    name: str
    phone: str
    address: str | None = None
    neighborhood: str | None = None
    notes: str | None = None
    loyalty_points: int = 0
    # Ja pode usar a recompensa da fidelidade no proximo pedido
    reward_available: bool = False
    order_count: int = 0
    total_spent: Decimal = Decimal("0.00")
    last_order_at: datetime | None = None
    created_at: datetime


class CustomerUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=140)
    address: str | None = None
    neighborhood: str | None = Field(default=None, max_length=120)
    notes: str | None = None


class CouponOut(ORMModel):
    id: str
    code: str
    kind: str
    value: Decimal
    min_order: Decimal
    max_uses: int | None = None
    uses: int
    valid_until: date | None = None
    active: bool
    created_at: datetime


class CouponCreate(BaseModel):
    code: str = Field(min_length=2, max_length=40)
    kind: Literal["PERCENT", "FIXED"]
    value: Annotated[Decimal, Field(gt=0, max_digits=10, decimal_places=2)]
    min_order: Money = Decimal("0.00")
    max_uses: int | None = Field(default=None, ge=1)
    valid_until: date | None = None
    active: bool = True

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        code = value.strip().upper().replace(" ", "")
        if not code:
            raise ValueError("Informe o codigo do cupom")
        return code


class CouponUpdate(BaseModel):
    value: Annotated[Decimal, Field(gt=0, max_digits=10, decimal_places=2)] | None = None
    min_order: Money | None = None
    max_uses: int | None = Field(default=None, ge=1)
    valid_until: date | None = None
    active: bool | None = None


class CouponCheck(BaseModel):
    code: str = Field(max_length=40)
    subtotal: Money


class CouponCheckResult(BaseModel):
    valid: bool
    discount: Decimal = Decimal("0.00")
    message: str
