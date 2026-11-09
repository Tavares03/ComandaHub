from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.deps import admin_access, get_current_user, require_establishment_access, require_roles
from app.core.security import hash_password
from app.db import get_db
from app.models.establishment import Establishment
from app.models.user import EstablishmentMembership, User, UserRole
from app.schemas.establishment import (
    EstablishmentOut,
    EstablishmentUpdate,
    EstablishmentUserCreate,
    EstablishmentUserOut,
    EstablishmentUserUpdate,
    EstablishmentWithRole,
)

router = APIRouter()


@router.get("", response_model=list[EstablishmentWithRole])
def list_establishments(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[EstablishmentWithRole]:
    rows = db.execute(
        select(Establishment, EstablishmentMembership.role)
        .join(EstablishmentMembership, EstablishmentMembership.establishment_id == Establishment.id)
        .where(EstablishmentMembership.user_id == current_user.id)
        .order_by(Establishment.name)
    ).all()
    return [
        EstablishmentWithRole.model_validate(EstablishmentOut.model_validate(est).model_dump() | {"role": role})
        for est, role in rows
    ]


@router.get("/{establishment_id}", response_model=EstablishmentOut)
def get_establishment(access=Depends(require_establishment_access)) -> Establishment:
    establishment, _membership = access
    return establishment


@router.patch("/{establishment_id}", response_model=EstablishmentOut)
def update_establishment(
    payload: EstablishmentUpdate,
    access=Depends(require_establishment_access),
    db: Session = Depends(get_db),
) -> Establishment:
    establishment, membership = access
    require_roles(membership, {UserRole.ADMIN})
    data = payload.model_dump(exclude_unset=True)
    if data.get("channel_commissions") is not None:
        data["channel_commissions"] = {
            (channel.value if hasattr(channel, "value") else str(channel)): str(value) for channel, value in data["channel_commissions"].items()
        }
    for field, value in data.items():
        setattr(establishment, field, value)
    db.commit()
    db.refresh(establishment)
    return establishment


# ------------------------------------------------------------------ usuarios da loja


def _user_row(db: Session, establishment_id: str, user_id: str) -> tuple[User, EstablishmentMembership]:
    row = db.execute(
        select(User, EstablishmentMembership)
        .join(EstablishmentMembership, EstablishmentMembership.user_id == User.id)
        .where(EstablishmentMembership.establishment_id == establishment_id, User.id == user_id)
    ).first()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario nao encontrado nesta loja")
    return row[0], row[1]


def _out(user: User, role: UserRole) -> EstablishmentUserOut:
    return EstablishmentUserOut(id=user.id, name=user.name, email=user.email, is_active=user.is_active, role=role)


def _manages_all_stores_of(db: Session, admin_id: str, target_id: str) -> bool:
    """Nome e senha valem em todas as lojas do usuario: so pode mudar quem e administrador de todas elas."""
    target_stores = set(db.scalars(select(EstablishmentMembership.establishment_id).where(EstablishmentMembership.user_id == target_id)))
    admin_stores = set(
        db.scalars(
            select(EstablishmentMembership.establishment_id).where(
                EstablishmentMembership.user_id == admin_id, EstablishmentMembership.role == UserRole.ADMIN
            )
        )
    )
    return target_stores <= admin_stores


@router.get("/{establishment_id}/users", response_model=list[EstablishmentUserOut])
def list_establishment_users(access=Depends(admin_access), db: Session = Depends(get_db)) -> list[EstablishmentUserOut]:
    establishment, _membership = access
    rows = db.execute(
        select(User, EstablishmentMembership.role)
        .join(EstablishmentMembership, EstablishmentMembership.user_id == User.id)
        .where(EstablishmentMembership.establishment_id == establishment.id)
        .order_by(User.name)
    ).all()
    return [_out(user, role) for user, role in rows]


@router.post("/{establishment_id}/users", response_model=EstablishmentUserOut, status_code=201)
def add_establishment_user(
    payload: EstablishmentUserCreate,
    access=Depends(admin_access),
    db: Session = Depends(get_db),
) -> EstablishmentUserOut:
    """Cria o usuario ou, se o e-mail ja existe (outra loja), so da acesso a esta loja (a senha dele continua)."""
    establishment, _membership = access
    user = db.scalar(select(User).where(func.lower(User.email) == payload.email))
    if user is None:
        user = User(name=payload.name, email=payload.email, password_hash=hash_password(payload.password), is_active=True)
        db.add(user)
        db.flush()
    elif db.scalar(
        select(EstablishmentMembership.id).where(
            EstablishmentMembership.user_id == user.id, EstablishmentMembership.establishment_id == establishment.id
        )
    ):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Este e-mail ja tem acesso a esta loja")
    db.add(EstablishmentMembership(user_id=user.id, establishment_id=establishment.id, role=payload.role))
    db.commit()
    return _out(user, payload.role)


@router.patch("/{establishment_id}/users/{user_id}", response_model=EstablishmentUserOut)
def update_establishment_user(
    user_id: str,
    payload: EstablishmentUserUpdate,
    access=Depends(admin_access),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> EstablishmentUserOut:
    establishment, _membership = access
    user, membership = _user_row(db, establishment.id, user_id)
    if payload.role is not None and payload.role != membership.role:
        if user.id == current_user.id:
            # Garante que a loja nunca fica sem administrador
            raise HTTPException(status_code=422, detail="Voce nao pode mudar o seu proprio perfil")
        membership.role = payload.role
    if payload.name is not None or payload.password is not None:
        if user.id != current_user.id and not _manages_all_stores_of(db, current_user.id, user.id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Este usuario tambem trabalha em outra loja; so quem administra todas as lojas dele pode mudar nome ou senha",
            )
        if payload.name is not None:
            user.name = payload.name.strip()
        if payload.password is not None:
            user.password_hash = hash_password(payload.password)
    db.commit()
    return _out(user, membership.role)


@router.delete("/{establishment_id}/users/{user_id}", status_code=204)
def remove_establishment_user(
    user_id: str,
    access=Depends(admin_access),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    """Tira o acesso a esta loja (o usuario continua existindo nas outras lojas)."""
    establishment, _membership = access
    _user, membership = _user_row(db, establishment.id, user_id)
    if user_id == current_user.id:
        raise HTTPException(status_code=422, detail="Voce nao pode remover o seu proprio acesso")
    db.delete(membership)
    db.commit()
    return Response(status_code=204)
