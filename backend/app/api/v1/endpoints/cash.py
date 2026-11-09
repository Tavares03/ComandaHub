from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_establishment_access, require_roles, staff_access
from app.db import get_db
from app.models.user import User, UserRole
from app.schemas.cash import CashClose, CashMovementCreate, CashOpen, CashSummary
from app.services import cash_service

router = APIRouter()

CASHIERS = {UserRole.ADMIN, UserRole.ATTENDANT}


@router.get("/{establishment_id}/cash/current", response_model=CashSummary | None)
def current_cash(access=Depends(staff_access), db: Session = Depends(get_db)) -> CashSummary | None:
    """Caixa aberto agora (com o resumo do turno) ou null se estiver fechado."""
    establishment, _membership = access
    session = cash_service.current_session(db, establishment.id)
    return cash_service.summarize(db, session) if session else None


@router.post("/{establishment_id}/cash/open", response_model=CashSummary, status_code=201)
def open_cash(
    payload: CashOpen,
    access=Depends(require_establishment_access),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CashSummary:
    establishment, membership = access
    require_roles(membership, CASHIERS)
    session = cash_service.open_session(db, establishment.id, user, payload.opening_amount, payload.notes)
    return cash_service.summarize(db, session)


@router.post("/{establishment_id}/cash/movements", response_model=CashSummary, status_code=201)
def cash_movement(
    payload: CashMovementCreate,
    access=Depends(require_establishment_access),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CashSummary:
    """Sangria (WITHDRAWAL) ou reforco (SUPPLY)."""
    establishment, membership = access
    require_roles(membership, CASHIERS)
    session = cash_service.add_movement(db, establishment.id, user, payload.kind, payload.amount, payload.note)
    return cash_service.summarize(db, session)


@router.post("/{establishment_id}/cash/close", response_model=CashSummary)
def close_cash(
    payload: CashClose,
    access=Depends(require_establishment_access),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CashSummary:
    establishment, membership = access
    require_roles(membership, CASHIERS)
    return cash_service.close_session(db, establishment.id, user, payload.counted_amount, payload.notes)


@router.get("/{establishment_id}/cash/sessions", response_model=list[CashSummary])
def cash_history(
    limit: int = Query(default=30, ge=1, le=100),
    access=Depends(staff_access),
    db: Session = Depends(get_db),
) -> list[CashSummary]:
    establishment, _membership = access
    return cash_service.history(db, establishment.id, limit)
