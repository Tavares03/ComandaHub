from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import admin_access, require_establishment_access, require_roles
from app.db import get_db
from app.models.delivery import Courier, DeliveryZone
from app.models.user import UserRole
from app.schemas.common import ORMModel
from app.services import report_service

router = APIRouter()

STAFF = {UserRole.ADMIN, UserRole.ATTENDANT}
Money = Annotated[Decimal, Field(ge=0, max_digits=10, decimal_places=2)]


class ZoneIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    fee: Money = Decimal("0.00")
    estimated_minutes: int | None = Field(default=None, ge=1, le=600)
    active: bool = True


class ZoneUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    fee: Money | None = None
    estimated_minutes: int | None = Field(default=None, ge=1, le=600)
    active: bool | None = None


class ZoneOut(ORMModel):
    id: str
    name: str
    fee: Decimal
    estimated_minutes: int | None = None
    active: bool


class CourierIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    phone: str | None = Field(default=None, max_length=40)
    fee_per_delivery: Money = Decimal("0.00")
    active: bool = True


class CourierUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    phone: str | None = Field(default=None, max_length=40)
    fee_per_delivery: Money | None = None
    active: bool | None = None


class CourierOut(ORMModel):
    id: str
    name: str
    phone: str | None = None
    fee_per_delivery: Decimal
    active: bool


class CourierReportRow(BaseModel):
    courier_id: str
    name: str
    deliveries: int
    # Soma das taxas de entrega cobradas dos clientes
    fees_charged: Decimal
    # Valor por entrega x entregas (ou as taxas cobradas, se o motoboy nao tem valor fixo)
    to_pay: Decimal


def _get(db: Session, model, establishment_id: str, item_id: str):
    item = db.scalar(select(model).where(model.id == item_id, model.establishment_id == establishment_id))
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Nao encontrado")
    return item


# ------------------------------------------------------------------ bairros


@router.get("/{establishment_id}/delivery-zones", response_model=list[ZoneOut])
def list_zones(access=Depends(require_establishment_access), db: Session = Depends(get_db)) -> list[DeliveryZone]:
    establishment, _membership = access
    return db.scalars(select(DeliveryZone).where(DeliveryZone.establishment_id == establishment.id).order_by(DeliveryZone.name)).all()


@router.post("/{establishment_id}/delivery-zones", response_model=ZoneOut, status_code=201)
def create_zone(payload: ZoneIn, access=Depends(require_establishment_access), db: Session = Depends(get_db)) -> DeliveryZone:
    establishment, membership = access
    require_roles(membership, STAFF)
    zone = DeliveryZone(establishment_id=establishment.id, **(payload.model_dump() | {"name": payload.name.strip()}))
    db.add(zone)
    db.commit()
    db.refresh(zone)
    return zone


@router.patch("/{establishment_id}/delivery-zones/{zone_id}", response_model=ZoneOut)
def update_zone(zone_id: str, payload: ZoneUpdate, access=Depends(require_establishment_access), db: Session = Depends(get_db)) -> DeliveryZone:
    establishment, membership = access
    require_roles(membership, STAFF)
    zone = _get(db, DeliveryZone, establishment.id, zone_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(zone, field, value)
    db.commit()
    db.refresh(zone)
    return zone


@router.delete("/{establishment_id}/delivery-zones/{zone_id}", status_code=204)
def delete_zone(zone_id: str, access=Depends(require_establishment_access), db: Session = Depends(get_db)) -> Response:
    establishment, membership = access
    require_roles(membership, STAFF)
    db.delete(_get(db, DeliveryZone, establishment.id, zone_id))
    db.commit()
    return Response(status_code=204)


# ------------------------------------------------------------------ motoboys


@router.get("/{establishment_id}/couriers", response_model=list[CourierOut])
def list_couriers(access=Depends(require_establishment_access), db: Session = Depends(get_db)) -> list[Courier]:
    establishment, _membership = access
    return db.scalars(select(Courier).where(Courier.establishment_id == establishment.id).order_by(Courier.name)).all()


@router.post("/{establishment_id}/couriers", response_model=CourierOut, status_code=201)
def create_courier(payload: CourierIn, access=Depends(require_establishment_access), db: Session = Depends(get_db)) -> Courier:
    establishment, membership = access
    require_roles(membership, STAFF)
    courier = Courier(establishment_id=establishment.id, **(payload.model_dump() | {"name": payload.name.strip()}))
    db.add(courier)
    db.commit()
    db.refresh(courier)
    return courier


@router.patch("/{establishment_id}/couriers/{courier_id}", response_model=CourierOut)
def update_courier(courier_id: str, payload: CourierUpdate, access=Depends(require_establishment_access), db: Session = Depends(get_db)) -> Courier:
    establishment, membership = access
    require_roles(membership, STAFF)
    courier = _get(db, Courier, establishment.id, courier_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(courier, field, value)
    db.commit()
    db.refresh(courier)
    return courier


@router.delete("/{establishment_id}/couriers/{courier_id}", status_code=204)
def delete_courier(courier_id: str, access=Depends(require_establishment_access), db: Session = Depends(get_db)) -> Response:
    establishment, membership = access
    require_roles(membership, STAFF)
    db.delete(_get(db, Courier, establishment.id, courier_id))
    db.commit()
    return Response(status_code=204)


@router.get("/{establishment_id}/couriers/report", response_model=list[CourierReportRow])
def courier_report(
    start: datetime | None = None,
    end: datetime | None = None,
    access=Depends(admin_access),
    db: Session = Depends(get_db),
) -> list[dict]:
    """Entregas por motoboy no periodo (pedidos nao cancelados) e quanto pagar."""
    establishment, _membership = access
    return report_service.courier_report(db, establishment.id, start, end)
