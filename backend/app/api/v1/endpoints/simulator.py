from __future__ import annotations

from pydantic import BaseModel, Field

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.deps import require_establishment_access, require_roles
from app.db import get_db
from app.models.order import OrderSource
from app.models.user import UserRole
from app.schemas.order import OrderOut
from app.services.simulation_service import simulate_orders

router = APIRouter()


class SimulateOrderRequest(BaseModel):
    source: OrderSource = OrderSource.IFOOD
    quantity: int = Field(default=1, ge=1, le=20)


@router.post("/{establishment_id}/simulate-order", response_model=list[OrderOut], status_code=201)
def simulate_order(
    payload: SimulateOrderRequest,
    access=Depends(require_establishment_access),
    db: Session = Depends(get_db),
):
    settings = get_settings()
    if settings.is_production:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Simulador indisponivel em producao")
    establishment, membership = access
    require_roles(membership, {UserRole.ADMIN, UserRole.ATTENDANT})
    return simulate_orders(db, establishment.id, payload.source, payload.quantity)
