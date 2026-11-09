from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import re

from pydantic import BaseModel, Field, field_validator

from app.models.catalog import SalesChannel
from app.models.user import UserRole
from app.schemas.common import ORMModel


class EstablishmentOut(ORMModel):
    id: str
    name: str
    legal_name: str | None = None
    tax_id: str | None = None
    phone: str | None = None
    address: str | None = None
    opening_hours: str | None = None
    logo_url: str | None = None
    timezone: str
    preparation_time: int
    loyalty_enabled: bool = False
    loyalty_goal: int = 10
    loyalty_reward: Decimal = Decimal("15.00")
    channel_commissions: dict[SalesChannel, Decimal] = {}
    slug: str | None = None
    whatsapp: str | None = None
    online_menu_enabled: bool = False
    online_orders_open: bool = True
    created_at: datetime
    updated_at: datetime


class EstablishmentWithRole(EstablishmentOut):
    role: UserRole


class EstablishmentUpdate(BaseModel):
    name: str | None = None
    legal_name: str | None = None
    tax_id: str | None = None
    phone: str | None = None
    address: str | None = None
    opening_hours: str | None = None
    logo_url: str | None = None
    preparation_time: int | None = None
    loyalty_enabled: bool | None = None
    loyalty_goal: int | None = Field(default=None, ge=1, le=100)
    loyalty_reward: Decimal | None = Field(default=None, ge=0, max_digits=10, decimal_places=2)
    channel_commissions: dict[SalesChannel, Decimal] | None = None
    slug: str | None = Field(default=None, max_length=80)
    whatsapp: str | None = Field(default=None, max_length=30)
    online_menu_enabled: bool | None = None
    online_orders_open: bool | None = None

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, value: str | None) -> str | None:
        if value is None:
            return None
        slug = value.strip().lower()
        if not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", slug) or len(slug) < 3:
            raise ValueError("Use so letras minusculas, numeros e hifen (ex.: burger-station)")
        return slug

    @field_validator("whatsapp")
    @classmethod
    def validate_whatsapp(cls, value: str | None) -> str | None:
        if value is None:
            return None
        digits = re.sub(r"\D", "", value)
        if digits and len(digits) < 10:
            raise ValueError("WhatsApp precisa de DDD + numero")
        return digits or None


class EstablishmentUserOut(ORMModel):
    id: str
    name: str
    email: str
    is_active: bool
    role: UserRole


EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class EstablishmentUserCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    # Sem EmailStr: dominios internos como ".local" tambem valem (ver LoginRequest)
    email: str = Field(min_length=5, max_length=255)
    # Ignorada se o e-mail ja existe em outra loja (o acesso e adicionado e a senha atual continua)
    password: str = Field(min_length=6, max_length=128)
    role: UserRole = UserRole.ATTENDANT

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        email = value.strip().lower()
        if not EMAIL_PATTERN.fullmatch(email):
            raise ValueError("E-mail invalido")
        return email

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        return value.strip()


class EstablishmentUserUpdate(BaseModel):
    role: UserRole | None = None
    name: str | None = Field(default=None, min_length=2, max_length=120)
    # Redefinir a senha de outra pessoa (ex.: funcionario esqueceu)
    password: str | None = Field(default=None, min_length=6, max_length=128)
