from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True, use_enum_values=True)


class MoneyMixin(BaseModel):
    price: Decimal = Field(max_digits=10, decimal_places=2)


class MessageResponse(BaseModel):
    message: str


class DateRange(BaseModel):
    start: datetime | None = None
    end: datetime | None = None
