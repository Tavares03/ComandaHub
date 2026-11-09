from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.deps import require_establishment_access, require_roles, staff_access
from app.db import get_db
from app.models.customer import Coupon, Customer
from app.models.user import UserRole
from app.schemas.customer import (
    CouponCheck,
    CouponCheckResult,
    CouponCreate,
    CouponOut,
    CouponUpdate,
    CustomerOut,
    CustomerUpdate,
)
from app.services import customer_service

router = APIRouter()

STAFF = {UserRole.ADMIN, UserRole.ATTENDANT}


# ------------------------------------------------------------------ clientes


@router.get("/{establishment_id}/customers", response_model=list[CustomerOut])
def list_customers(
    search: str | None = Query(default=None, max_length=80),
    limit: int = Query(default=50, ge=1, le=200),
    access=Depends(staff_access),
    db: Session = Depends(get_db),
) -> list[CustomerOut]:
    establishment, _membership = access
    query = select(Customer).where(Customer.establishment_id == establishment.id)
    if search and search.strip():
        term = f"%{search.strip().lower()}%"
        digits = customer_service.normalize_phone(search) or "".join(ch for ch in search if ch.isdigit())
        conditions = [func.lower(Customer.name).like(term)]
        if digits:
            conditions.append(Customer.phone.like(f"%{digits}%"))
        query = query.where(or_(*conditions))
    customers = db.scalars(query.order_by(Customer.updated_at.desc()).limit(limit)).all()
    return [customer_service.customer_out(db, customer, establishment) for customer in customers]


@router.get("/{establishment_id}/customers/lookup", response_model=CustomerOut | None)
def lookup_customer(phone: str = Query(max_length=30), access=Depends(staff_access), db: Session = Depends(get_db)) -> CustomerOut | None:
    """Busca pelo telefone para preencher o pedido (null se nao conhece)."""
    establishment, _membership = access
    customer = customer_service.find_by_phone(db, establishment.id, phone)
    return customer_service.customer_out(db, customer, establishment) if customer else None


@router.patch("/{establishment_id}/customers/{customer_id}", response_model=CustomerOut)
def update_customer(
    customer_id: str,
    payload: CustomerUpdate,
    access=Depends(require_establishment_access),
    db: Session = Depends(get_db),
) -> CustomerOut:
    establishment, membership = access
    require_roles(membership, STAFF)
    customer = db.scalar(select(Customer).where(Customer.id == customer_id, Customer.establishment_id == establishment.id))
    if not customer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cliente nao encontrado")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(customer, field, value)
    db.commit()
    db.refresh(customer)
    return customer_service.customer_out(db, customer, establishment)


# ------------------------------------------------------------------ cupons


def _coupon_or_404(db: Session, establishment_id: str, coupon_id: str) -> Coupon:
    coupon = db.scalar(select(Coupon).where(Coupon.id == coupon_id, Coupon.establishment_id == establishment_id))
    if not coupon:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cupom nao encontrado")
    return coupon


@router.get("/{establishment_id}/coupons", response_model=list[CouponOut])
def list_coupons(access=Depends(staff_access), db: Session = Depends(get_db)) -> list[Coupon]:
    establishment, _membership = access
    return db.scalars(select(Coupon).where(Coupon.establishment_id == establishment.id).order_by(Coupon.created_at.desc())).all()


@router.post("/{establishment_id}/coupons", response_model=CouponOut, status_code=201)
def create_coupon(payload: CouponCreate, access=Depends(require_establishment_access), db: Session = Depends(get_db)) -> Coupon:
    establishment, membership = access
    require_roles(membership, {UserRole.ADMIN})
    if payload.kind == "PERCENT" and payload.value > 100:
        raise HTTPException(status_code=422, detail="Percentual maximo e 100%")
    coupon = Coupon(establishment_id=establishment.id, uses=0, **payload.model_dump())
    db.add(coupon)
    db.commit()
    db.refresh(coupon)
    return coupon


@router.patch("/{establishment_id}/coupons/{coupon_id}", response_model=CouponOut)
def update_coupon(
    coupon_id: str,
    payload: CouponUpdate,
    access=Depends(require_establishment_access),
    db: Session = Depends(get_db),
) -> Coupon:
    establishment, membership = access
    require_roles(membership, {UserRole.ADMIN})
    coupon = _coupon_or_404(db, establishment.id, coupon_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(coupon, field, value)
    db.commit()
    db.refresh(coupon)
    return coupon


@router.delete("/{establishment_id}/coupons/{coupon_id}", status_code=204)
def delete_coupon(coupon_id: str, access=Depends(require_establishment_access), db: Session = Depends(get_db)) -> Response:
    establishment, membership = access
    require_roles(membership, {UserRole.ADMIN})
    db.delete(_coupon_or_404(db, establishment.id, coupon_id))
    db.commit()
    return Response(status_code=204)


@router.post("/{establishment_id}/coupons/validate", response_model=CouponCheckResult)
def validate_coupon(payload: CouponCheck, access=Depends(staff_access), db: Session = Depends(get_db)) -> CouponCheckResult:
    """Previa do desconto antes de fechar o pedido."""
    establishment, _membership = access
    try:
        _coupon, discount = customer_service.check_coupon(db, establishment.id, payload.code, payload.subtotal)
    except HTTPException as exc:
        return CouponCheckResult(valid=False, message=str(exc.detail))
    return CouponCheckResult(valid=True, discount=discount, message=f"Desconto de R$ {discount:.2f}")
