from __future__ import annotations

from collections import defaultdict
from datetime import timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.deps import staff_access
from app.core.timeutils import local_day_bounds, to_local
from app.db import get_db
from app.models.order import Order, OrderStatus
from app.schemas.dashboard import DashboardResponse
from app.services.order_service import ACTIVE_STATUSES

router = APIRouter()


@router.get("/{establishment_id}/dashboard", response_model=DashboardResponse)
def dashboard(access=Depends(staff_access), db: Session = Depends(get_db)) -> DashboardResponse:
    establishment, _membership = access
    tz_name = establishment.timezone
    today_start, today_end = local_day_bounds(tz_name)
    week_start = today_start - timedelta(days=6)

    # Uma unica consulta leve para a semana; agregacoes por dia/hora no fuso da loja sao feitas em Python
    # (funciona igual em PostgreSQL e SQLite e evita o "dia" virar as 21h no horario de Brasilia).
    week_rows = db.execute(
        select(Order.created_at, Order.status, Order.source, Order.total).where(
            Order.establishment_id == establishment.id,
            Order.created_at >= week_start.astimezone(timezone.utc),
            Order.created_at < today_end.astimezone(timezone.utc),
        )
    ).all()

    orders_today = finished_today = canceled_today = 0
    revenue_today = 0.0
    channel_totals: dict[str, dict] = defaultdict(lambda: {"total": 0.0, "orders": 0})
    hour_counts: dict[int, int] = defaultdict(int)
    day_totals: dict[str, float] = defaultdict(float)

    for created_at, status, source, total in week_rows:
        local_created = to_local(created_at, tz_name)
        value = float(total or 0)
        if status == OrderStatus.FINISHED:
            day_totals[local_created.date().isoformat()] += value
        if local_created < today_start:
            continue
        orders_today += 1
        if status == OrderStatus.FINISHED:
            finished_today += 1
            revenue_today += value
        if status == OrderStatus.CANCELED:
            canceled_today += 1
            continue
        channel_totals[source.value]["total"] += value
        channel_totals[source.value]["orders"] += 1
        hour_counts[local_created.hour] += 1

    in_progress = len(
        db.scalars(
            select(Order.id).where(Order.establishment_id == establishment.id, Order.status.in_(ACTIVE_STATUSES))
        ).all()
    )

    recent_orders = db.scalars(
        select(Order)
        .where(Order.establishment_id == establishment.id)
        .options(selectinload(Order.items), selectinload(Order.events))
        .order_by(Order.created_at.desc())
        .limit(8)
    ).all()

    return DashboardResponse(
        orders_today=orders_today,
        in_progress=in_progress,
        finished_today=finished_today,
        canceled_today=canceled_today,
        gross_revenue_today=round(revenue_today, 2),
        average_ticket_today=round(revenue_today / finished_today, 2) if finished_today else 0,
        sales_by_channel=[{"source": source, **values} for source, values in channel_totals.items()],
        orders_by_hour=[{"hour": hour, "orders": hour_counts.get(hour, 0)} for hour in range(24)],
        sales_last_7_days=[
            {
                "date": (week_start + timedelta(days=index)).date().isoformat(),
                "total": round(day_totals.get((week_start + timedelta(days=index)).date().isoformat(), 0.0), 2),
            }
            for index in range(7)
        ],
        recent_orders=recent_orders,
    )
