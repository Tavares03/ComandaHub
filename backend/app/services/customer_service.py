"""Clientes (pelo telefone), cupons e fidelidade aplicados aos pedidos da loja."""
from __future__ import annotations

import re
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.timeutils import local_now
from app.models.customer import Coupon, Customer
from app.models.establishment import Establishment
from app.models.order import Order, OrderStatus
from app.schemas.customer import CustomerOut

ZERO = Decimal("0.00")


def normalize_phone(phone: str | None) -> str | None:
    """So os digitos; ignora DDI 55 quando vier com 12/13 digitos."""
    digits = re.sub(r"\D", "", phone or "")
    if len(digits) in (12, 13) and digits.startswith("55"):
        digits = digits[2:]
    return digits if len(digits) >= 8 else None


def find_by_phone(db: Session, establishment_id: str, phone: str | None) -> Customer | None:
    digits = normalize_phone(phone)
    if not digits:
        return None
    return db.scalar(select(Customer).where(Customer.establishment_id == establishment_id, Customer.phone == digits))


def upsert_from_order(db: Session, establishment_id: str, phone: str | None, name: str | None,
                      address: str | None, neighborhood: str | None = None, overwrite: bool = True) -> Customer | None:
    """Cria/atualiza o cliente pelo telefone.

    overwrite=False (cardapio publico, sem login): um cliente ja cadastrado so ganha os dados que
    faltam, para ninguem trocar o nome/endereco de outra pessoa digitando o telefone dela.
    """
    digits = normalize_phone(phone)
    if not digits:
        return None
    customer = find_by_phone(db, establishment_id, digits)
    is_new = customer is None
    if customer is None:
        customer = Customer(establishment_id=establishment_id, phone=digits, name=(name or "").strip() or "Cliente", loyalty_points=0)
        db.add(customer)
    can_replace = overwrite or is_new
    if name and name.strip() and (can_replace or customer.name in ("", "Cliente")):
        customer.name = name.strip()
    if address and address.strip() and (can_replace or not customer.address):
        customer.address = address.strip()
    if neighborhood and neighborhood.strip() and (can_replace or not customer.neighborhood):
        customer.neighborhood = neighborhood.strip()
    db.flush()
    return customer


def customer_out(db: Session, customer: Customer, establishment: Establishment) -> CustomerOut:
    count, total, last = db.execute(
        select(func.count(Order.id), func.coalesce(func.sum(Order.total), 0), func.max(Order.created_at))
        .where(Order.customer_id == customer.id, Order.status != OrderStatus.CANCELED)
    ).one()
    return CustomerOut(
        id=customer.id,
        name=customer.name,
        phone=customer.phone,
        address=customer.address,
        neighborhood=customer.neighborhood,
        notes=customer.notes,
        loyalty_points=customer.loyalty_points,
        reward_available=bool(establishment.loyalty_enabled and customer.loyalty_points >= establishment.loyalty_goal),
        order_count=count,
        total_spent=Decimal(total or 0).quantize(Decimal("0.01")),
        last_order_at=last,
        created_at=customer.created_at,
    )


# ------------------------------------------------------------------ cupons


def coupon_discount(coupon: Coupon, subtotal: Decimal) -> Decimal:
    if coupon.kind == "PERCENT":
        value = (subtotal * Decimal(coupon.value) / 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    else:
        value = Decimal(coupon.value)
    return min(value, subtotal).quantize(Decimal("0.01"))


def check_coupon(db: Session, establishment_id: str, code: str, subtotal: Decimal, today: date | None = None) -> tuple[Coupon, Decimal]:
    """Valida o cupom para este subtotal. Erro 422 com o motivo quando nao vale."""
    normalized = (code or "").strip().upper().replace(" ", "")
    coupon = db.scalar(select(Coupon).where(Coupon.establishment_id == establishment_id, Coupon.code == normalized))
    if not coupon or not coupon.active:
        raise HTTPException(status_code=422, detail="Cupom invalido ou desativado")
    if today is None:
        # "Valido ate" e o dia inteiro no fuso da loja (o servidor costuma rodar em UTC)
        today = local_now(db.scalar(select(Establishment.timezone).where(Establishment.id == establishment_id))).date()
    if coupon.valid_until and today > coupon.valid_until:
        raise HTTPException(status_code=422, detail="Cupom vencido")
    if coupon.max_uses is not None and coupon.uses >= coupon.max_uses:
        raise HTTPException(status_code=422, detail="Cupom esgotado")
    if subtotal < Decimal(coupon.min_order or 0):
        raise HTTPException(status_code=422, detail=f"Cupom vale para pedidos a partir de R$ {Decimal(coupon.min_order):.2f} (pedido minimo)")
    return coupon, coupon_discount(coupon, subtotal)


# ------------------------------------------------------------------ fidelidade


def check_reward(establishment: Establishment, customer: Customer | None) -> Decimal:
    if not establishment.loyalty_enabled:
        raise HTTPException(status_code=422, detail="O programa de fidelidade esta desligado")
    if customer is None:
        raise HTTPException(status_code=422, detail="Informe o telefone do cliente para usar a fidelidade")
    if customer.loyalty_points < establishment.loyalty_goal:
        missing = establishment.loyalty_goal - customer.loyalty_points
        raise HTTPException(status_code=422, detail=f"Faltam {missing} pedido(s) para a recompensa da fidelidade")
    return Decimal(establishment.loyalty_reward)


def register_order(db: Session, establishment: Establishment, order: Order, customer: Customer | None,
                   coupon: Coupon | None, reward_used: bool) -> None:
    """Depois do pedido criado: liga cliente e cupom, conta o uso e desconta a recompensa usada.

    O ponto da fidelidade so entra quando o pedido e finalizado (award_loyalty_point), para que
    pedidos falsos ou cancelados nao contem.
    """
    if customer is not None:
        order.customer_id = customer.id
        if reward_used:
            order.loyalty_points_delta = -establishment.loyalty_goal
            customer.loyalty_points = max(0, customer.loyalty_points + order.loyalty_points_delta)
    if coupon is not None:
        order.coupon_code = coupon.code
        coupon.uses += 1


def award_loyalty_point(db: Session, order: Order) -> None:
    """Pedido finalizado com telefone ganha 1 ponto (pedido que usou a recompensa nao pontua)."""
    if not order.customer_id or order.loyalty_points_delta:
        return
    establishment = db.get(Establishment, order.establishment_id)
    customer = db.get(Customer, order.customer_id)
    if establishment is None or customer is None or not establishment.loyalty_enabled:
        return
    order.loyalty_points_delta = 1
    customer.loyalty_points += 1


def revert_order(db: Session, order: Order) -> None:
    """Cancelamento: devolve o uso do cupom e desfaz os pontos do pedido."""
    if order.coupon_code:
        coupon = db.scalar(select(Coupon).where(Coupon.establishment_id == order.establishment_id, Coupon.code == order.coupon_code))
        if coupon and coupon.uses > 0:
            coupon.uses -= 1
    if order.customer_id and order.loyalty_points_delta:
        customer = db.get(Customer, order.customer_id)
        if customer:
            customer.loyalty_points = max(0, customer.loyalty_points - order.loyalty_points_delta)
        order.loyalty_points_delta = 0
