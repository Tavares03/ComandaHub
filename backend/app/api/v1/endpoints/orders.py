from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.deps import require_establishment_access, require_roles
from app.core.timeutils import local_day_bounds
from app.db import get_db
from app.models.order import Order, OrderSource, OrderStatus
from app.models.user import UserRole
from app.schemas.order import (
    LocalOrderCreate,
    OrderCourierUpdate,
    OrderListResponse,
    OrderOut,
    OrderPaymentUpdate,
    OrderStatusUpdate,
    PendingCount,
)
from app.services.order_service import (
    ACTIVE_STATUSES,
    TERMINAL_STATUSES,
    assign_courier,
    create_local_order,
    get_order_or_404,
    update_order_status,
    update_payment_status,
)

router = APIRouter()

STAFF_ROLES = {UserRole.ADMIN, UserRole.ATTENDANT}


@router.get("/{establishment_id}/orders", response_model=OrderListResponse)
def list_orders(
    access=Depends(require_establishment_access),
    db: Session = Depends(get_db),
    status_filter: OrderStatus | None = Query(default=None, alias="status"),
    source: OrderSource | None = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    search: str | None = Query(default=None, max_length=80),
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> OrderListResponse:
    establishment, _membership = access
    filters = [Order.establishment_id == establishment.id]
    if status_filter:
        filters.append(Order.status == status_filter)
    if source:
        filters.append(Order.source == source)
    if created_from:
        filters.append(Order.created_at >= created_from)
    if created_to:
        filters.append(Order.created_at <= created_to)
    if search:
        term = f"%{search.strip().lower()}%"
        filters.append(
            or_(
                func.lower(Order.order_number).like(term),
                func.lower(func.coalesce(Order.customer_name, "")).like(term),
                func.coalesce(Order.customer_phone, "").like(term),
            )
        )
    total = db.scalar(select(func.count(Order.id)).where(*filters)) or 0
    items = db.scalars(
        select(Order)
        .where(*filters)
        .options(selectinload(Order.items), selectinload(Order.events))
        .order_by(Order.created_at.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return OrderListResponse(items=items, total=total, limit=limit, offset=offset)


@router.get("/{establishment_id}/orders/board", response_model=OrderListResponse)
def order_board(access=Depends(require_establishment_access), db: Session = Depends(get_db)) -> OrderListResponse:
    """Kanban: todos os pedidos em andamento (sem limite) + finalizados/cancelados do dia local."""
    establishment, _membership = access
    today_start, _today_end = local_day_bounds(establishment.timezone)
    items = db.scalars(
        select(Order)
        .where(
            Order.establishment_id == establishment.id,
            or_(
                Order.status.in_(ACTIVE_STATUSES),
                and_(Order.status.in_(TERMINAL_STATUSES), Order.updated_at >= today_start.astimezone(timezone.utc)),
            ),
        )
        .options(selectinload(Order.items), selectinload(Order.events))
        .order_by(Order.created_at.asc())
    ).all()
    return OrderListResponse(items=items, total=len(items), limit=len(items), offset=0)


@router.get("/{establishment_id}/orders/pending-count", response_model=PendingCount)
def pending_count(access=Depends(require_establishment_access), db: Session = Depends(get_db)) -> PendingCount:
    """Pedidos novos esperando aceite (sino do topo da tela)."""
    establishment, _membership = access
    count = db.scalar(
        select(func.count(Order.id)).where(Order.establishment_id == establishment.id, Order.status == OrderStatus.NEW)
    )
    return PendingCount(new_orders=count or 0)


@router.get("/{establishment_id}/orders/{order_id}", response_model=OrderOut)
def get_order(order_id: str, access=Depends(require_establishment_access), db: Session = Depends(get_db)) -> Order:
    establishment, _membership = access
    return get_order_or_404(db, establishment.id, order_id)


@router.post("/{establishment_id}/orders", response_model=OrderOut, status_code=201)
def create_order_endpoint(
    payload: LocalOrderCreate,
    access=Depends(require_establishment_access),
    db: Session = Depends(get_db),
) -> Order:
    establishment, membership = access
    require_roles(membership, STAFF_ROLES)
    return create_local_order(db, establishment.id, payload)


@router.patch("/{establishment_id}/orders/{order_id}/status", response_model=OrderOut)
def change_order_status(
    order_id: str,
    payload: OrderStatusUpdate,
    access=Depends(require_establishment_access),
    db: Session = Depends(get_db),
) -> Order:
    establishment, membership = access
    # Cozinha movimenta o preparo; cancelar e decisao do atendimento/gerencia.
    if payload.status == OrderStatus.CANCELED:
        require_roles(membership, STAFF_ROLES)
    else:
        require_roles(membership, STAFF_ROLES | {UserRole.KITCHEN})
    return update_order_status(db, establishment.id, order_id, payload.status, payload.cancel_reason, payload.courier_id)


@router.patch("/{establishment_id}/orders/{order_id}/courier", response_model=OrderOut)
def change_order_courier(
    order_id: str,
    payload: OrderCourierUpdate,
    access=Depends(require_establishment_access),
    db: Session = Depends(get_db),
) -> Order:
    establishment, membership = access
    require_roles(membership, STAFF_ROLES)
    order = get_order_or_404(db, establishment.id, order_id)
    assign_courier(db, establishment.id, order, payload.courier_id)
    db.commit()
    return get_order_or_404(db, establishment.id, order_id)


@router.patch("/{establishment_id}/orders/{order_id}/payment", response_model=OrderOut)
def change_payment_status(
    order_id: str,
    payload: OrderPaymentUpdate,
    access=Depends(require_establishment_access),
    db: Session = Depends(get_db),
) -> Order:
    establishment, membership = access
    require_roles(membership, STAFF_ROLES)
    return update_payment_status(db, establishment.id, order_id, payload.payment_status)
