"""Caixa da loja: um turno aberto por vez; o resumo soma os pedidos criados durante o turno."""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.cash import CashMovement, CashSession
from app.models.order import Order, OrderStatus, PaymentMethod
from app.models.user import User
from app.schemas.cash import CashMovementOut, CashSummary, SalesByMethod

ZERO = Decimal("0.00")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _money(value) -> Decimal:
    return Decimal(value or 0).quantize(Decimal("0.01"))


def current_session(db: Session, establishment_id: str) -> CashSession | None:
    return db.scalar(
        select(CashSession)
        .where(CashSession.establishment_id == establishment_id, CashSession.closed_at.is_(None))
        .options(selectinload(CashSession.movements).selectinload(CashMovement.user), selectinload(CashSession.opened_by))
        .order_by(CashSession.opened_at.desc())
    )


def require_open(db: Session, establishment_id: str) -> CashSession:
    session = current_session(db, establishment_id)
    if not session:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="O caixa esta fechado")
    return session


def open_session(db: Session, establishment_id: str, user: User, opening_amount: Decimal, notes: str | None) -> CashSession:
    if current_session(db, establishment_id):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Ja existe um caixa aberto nesta loja")
    session = CashSession(
        establishment_id=establishment_id,
        opened_at=_now(),
        opened_by_id=user.id,
        opening_amount=_money(opening_amount),
        notes=notes,
    )
    db.add(session)
    db.commit()
    return current_session(db, establishment_id)


def add_movement(db: Session, establishment_id: str, user: User, kind: str, amount: Decimal, note: str | None) -> CashSession:
    session = require_open(db, establishment_id)
    session.movements.append(CashMovement(kind=kind, amount=_money(amount), note=note, user_id=user.id, created_at=_now()))
    db.commit()
    return current_session(db, establishment_id)


def summarize(db: Session, session: CashSession) -> CashSummary:
    end = session.closed_at or _now()
    window = [Order.establishment_id == session.establishment_id, Order.created_at >= session.opened_at, Order.created_at <= end]
    rows = db.execute(
        select(Order.payment_method, func.count(Order.id), func.coalesce(func.sum(Order.total), 0))
        .where(*window, Order.status != OrderStatus.CANCELED)
        .group_by(Order.payment_method)
    ).all()
    sales = [SalesByMethod(payment_method=method, orders=count, total=_money(total)) for method, count, total in rows]
    sales.sort(key=lambda row: row.total, reverse=True)
    canceled = db.scalar(select(func.count(Order.id)).where(*window, Order.status == OrderStatus.CANCELED)) or 0
    cash_sales = sum((row.total for row in sales if row.payment_method == PaymentMethod.CASH), ZERO)
    withdrawals = sum((_money(m.amount) for m in session.movements if m.kind == "WITHDRAWAL"), ZERO)
    supplies = sum((_money(m.amount) for m in session.movements if m.kind == "SUPPLY"), ZERO)
    expected = _money(session.opening_amount) + cash_sales + supplies - withdrawals
    counted = _money(session.counted_amount) if session.counted_amount is not None else None
    return CashSummary(
        id=session.id,
        opened_at=session.opened_at,
        opened_by_name=session.opened_by.name if session.opened_by else None,
        opening_amount=_money(session.opening_amount),
        closed_at=session.closed_at,
        closed_by_name=session.closed_by.name if session.closed_by else None,
        counted_amount=counted,
        notes=session.notes,
        order_count=sum(row.orders for row in sales),
        canceled_count=canceled,
        total_sales=sum((row.total for row in sales), ZERO),
        sales_by_method=sales,
        withdrawals=withdrawals,
        supplies=supplies,
        expected_cash=expected,
        difference=(counted - expected) if counted is not None else None,
        movements=[
            CashMovementOut(id=m.id, kind=m.kind, amount=_money(m.amount), note=m.note,
                            user_name=m.user.name if m.user else None, created_at=m.created_at)
            for m in session.movements
        ],
    )


def close_session(db: Session, establishment_id: str, user: User, counted: Decimal, notes: str | None) -> CashSummary:
    session = require_open(db, establishment_id)
    summary = summarize(db, session)
    session.closed_at = _now()
    session.closed_by_id = user.id
    session.counted_amount = _money(counted)
    session.expected_cash = summary.expected_cash
    session.total_sales = summary.total_sales
    if notes:
        session.notes = f"{session.notes}\n{notes}" if session.notes else notes
    db.commit()
    return summarize(db, get_session(db, establishment_id, session.id))


def get_session(db: Session, establishment_id: str, session_id: str) -> CashSession:
    session = db.scalar(
        select(CashSession)
        .where(CashSession.id == session_id, CashSession.establishment_id == establishment_id)
        .options(
            selectinload(CashSession.movements).selectinload(CashMovement.user),
            selectinload(CashSession.opened_by),
            selectinload(CashSession.closed_by),
        )
        .execution_options(populate_existing=True)
    )
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Caixa nao encontrado")
    return session


def history(db: Session, establishment_id: str, limit: int = 30) -> list[CashSummary]:
    sessions = db.scalars(
        select(CashSession)
        .where(CashSession.establishment_id == establishment_id)
        .options(
            selectinload(CashSession.movements).selectinload(CashMovement.user),
            selectinload(CashSession.opened_by),
            selectinload(CashSession.closed_by),
        )
        .order_by(CashSession.opened_at.desc())
        .limit(limit)
    ).all()
    return [summarize(db, session) for session in sessions]
