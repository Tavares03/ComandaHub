from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.catalog import SalesChannel
from app.models.delivery import Courier
from app.models.establishment import Establishment
from app.models.order import Order, OrderItem, OrderStatus
from app.services.availability import channel_for_source

CENTS = Decimal("0.01")


def as_float(value) -> float:
    return float(value or 0)


def default_range(start: datetime | None, end: datetime | None) -> tuple[datetime, datetime]:
    now = datetime.now(timezone.utc)
    return start or (now - timedelta(days=7)), end or now


def report_overview(db: Session, establishment_id: str, start: datetime | None, end: datetime | None) -> dict:
    start_dt, end_dt = default_range(start, end)
    base = [Order.establishment_id == establishment_id, Order.created_at >= start_dt, Order.created_at <= end_dt]
    total_sold = db.scalar(select(func.coalesce(func.sum(Order.total), 0)).where(*base, Order.status == OrderStatus.FINISHED))
    finished_count = db.scalar(select(func.count(Order.id)).where(*base, Order.status == OrderStatus.FINISHED)) or 0
    canceled_count = db.scalar(select(func.count(Order.id)).where(*base, Order.status == OrderStatus.CANCELED)) or 0
    in_progress_count = db.scalar(
        select(func.count(Order.id)).where(
            *base,
            Order.status.in_([OrderStatus.NEW, OrderStatus.ACCEPTED, OrderStatus.PREPARING, OrderStatus.READY, OrderStatus.OUT_FOR_DELIVERY]),
        )
    ) or 0
    average_ticket = as_float(total_sold) / finished_count if finished_count else 0
    return {
        "total_sold": as_float(total_sold),
        "order_count": finished_count + canceled_count + in_progress_count,
        "average_ticket": average_ticket,
        "canceled_count": canceled_count,
        "in_progress_count": in_progress_count,
        "finished_count": finished_count,
    }


def sales_by_channel(db: Session, establishment_id: str, start: datetime | None, end: datetime | None) -> list[dict]:
    start_dt, end_dt = default_range(start, end)
    rows = db.execute(
        select(Order.source, func.coalesce(func.sum(Order.total), 0), func.count(Order.id))
        .where(
            Order.establishment_id == establishment_id,
            Order.created_at >= start_dt,
            Order.created_at <= end_dt,
            Order.status == OrderStatus.FINISHED,
        )
        .group_by(Order.source)
    ).all()
    return [{"source": row[0].value, "total": as_float(row[1]), "orders": row[2]} for row in rows]


def top_products(db: Session, establishment_id: str, start: datetime | None, end: datetime | None) -> list[dict]:
    start_dt, end_dt = default_range(start, end)
    rows = db.execute(
        select(OrderItem.product_name, func.coalesce(func.sum(OrderItem.quantity), 0), func.coalesce(func.sum(OrderItem.total), 0))
        .join(Order, Order.id == OrderItem.order_id)
        .where(
            Order.establishment_id == establishment_id,
            Order.created_at >= start_dt,
            Order.created_at <= end_dt,
            Order.status == OrderStatus.FINISHED,
        )
        .group_by(OrderItem.product_name)
        .order_by(func.sum(OrderItem.quantity).desc())
        .limit(10)
    ).all()
    return [{"product_name": row[0], "quantity": int(row[1]), "total": as_float(row[2])} for row in rows]


def courier_report(db: Session, establishment_id: str, start: datetime | None, end: datetime | None) -> list[dict]:
    start_dt, end_dt = default_range(start, end)
    rows = db.execute(
        select(Courier.id, Courier.name, Courier.fee_per_delivery, func.count(Order.id), func.coalesce(func.sum(Order.delivery_fee), 0))
        .join(Order, Order.courier_id == Courier.id)
        .where(
            Courier.establishment_id == establishment_id,
            Order.created_at >= start_dt,
            Order.created_at <= end_dt,
            Order.status != OrderStatus.CANCELED,
        )
        .group_by(Courier.id, Courier.name, Courier.fee_per_delivery)
        .order_by(func.count(Order.id).desc())
    ).all()
    report = []
    for courier_id, name, per_delivery, deliveries, fees in rows:
        fees = Decimal(fees or 0).quantize(CENTS)
        per_delivery = Decimal(per_delivery or 0)
        to_pay = (per_delivery * deliveries).quantize(CENTS) if per_delivery > 0 else fees
        report.append({"courier_id": courier_id, "name": name, "deliveries": deliveries, "fees_charged": fees, "to_pay": to_pay})
    return report


def profit_by_channel(db: Session, establishment_id: str, start: datetime | None, end: datetime | None) -> list[dict]:
    """Faturamento - comissao do canal - custo dos ingredientes (pedidos nao cancelados)."""
    start_dt, end_dt = default_range(start, end)
    establishment = db.get(Establishment, establishment_id)
    commissions = {key: Decimal(str(value)) for key, value in (establishment.channel_commissions or {}).items()}
    window = [
        Order.establishment_id == establishment_id,
        Order.created_at >= start_dt,
        Order.created_at <= end_dt,
        Order.status != OrderStatus.CANCELED,
    ]
    orders = db.execute(select(Order.id, Order.source, Order.total).where(*window)).all()
    costs = dict(
        db.execute(
            select(OrderItem.order_id, func.coalesce(func.sum(OrderItem.unit_cost * OrderItem.quantity), 0))
            .join(Order, Order.id == OrderItem.order_id)
            .where(*window)
            .group_by(OrderItem.order_id)
        ).all()
    )
    totals: dict[str, dict] = defaultdict(lambda: {"orders": 0, "revenue": Decimal("0"), "ingredient_cost": Decimal("0")})
    for order_id, source, total in orders:
        channel = channel_for_source(source).value
        totals[channel]["orders"] += 1
        totals[channel]["revenue"] += Decimal(total or 0)
        totals[channel]["ingredient_cost"] += Decimal(costs.get(order_id) or 0)
    report = []
    for channel in SalesChannel:
        data = totals.get(channel.value)
        if not data:
            continue
        revenue = data["revenue"].quantize(CENTS)
        rate = commissions.get(channel.value, Decimal("0"))
        commission = (revenue * rate / 100).quantize(CENTS)
        cost = data["ingredient_cost"].quantize(CENTS)
        profit = revenue - commission - cost
        report.append({
            "channel": channel.value,
            "orders": data["orders"],
            "revenue": revenue,
            "commission_rate": rate,
            "commission": commission,
            "ingredient_cost": cost,
            "profit": profit,
            "margin": (profit / revenue * 100).quantize(Decimal("0.1")) if revenue else Decimal("0"),
        })
    return report
