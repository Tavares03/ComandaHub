from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.models.user import UserRole
from app.schemas.common import ORMModel


class LoginRequest(BaseModel):
    # Login nao valida formato de e-mail: dominios internos como ".local" sao validos aqui
    # e o EmailStr do pydantic os rejeita como "special-use".
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=1, max_length=256)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()


class EstablishmentSummary(ORMModel):
    id: str
    name: str
    role: UserRole


class UserOut(ORMModel):
    id: str
    name: str
    email: str
    is_active: bool
    created_at: datetime


class AuthUser(UserOut):
    establishments: list[EstablishmentSummary]


class PasswordChange(BaseModel):
    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=6, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: AuthUser
