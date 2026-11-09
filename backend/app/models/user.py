from __future__ import annotations

from enum import Enum

from sqlalchemy import Boolean, Enum as SAEnum, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, IdMixin, TimestampMixin


class UserRole(str, Enum):
    ADMIN = "ADMIN"
    ATTENDANT = "ATTENDANT"
    KITCHEN = "KITCHEN"


class User(Base, IdMixin, TimestampMixin):
    __tablename__ = "users"

    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    memberships = relationship("EstablishmentMembership", back_populates="user", cascade="all, delete-orphan")


class EstablishmentMembership(Base, IdMixin):
    __tablename__ = "establishment_memberships"
    __table_args__ = (UniqueConstraint("user_id", "establishment_id", name="uq_membership_user_establishment"),)

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    establishment_id: Mapped[str] = mapped_column(ForeignKey("establishments.id", ondelete="CASCADE"), index=True)
    role: Mapped[UserRole] = mapped_column(SAEnum(UserRole, native_enum=False), default=UserRole.ATTENDANT)

    user = relationship("User", back_populates="memberships")
    establishment = relationship("Establishment", back_populates="memberships")
