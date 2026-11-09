from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import admin_access
from app.db import get_db
from app.schemas.report import ProfitByChannel, ReportOverview, SalesByChannel, TopProduct
from app.services import report_service

router = APIRouter()


@router.get("/{establishment_id}/reports/overview", response_model=ReportOverview)
def overview(
    start: datetime | None = None,
    end: datetime | None = None,
    access=Depends(admin_access),
    db: Session = Depends(get_db),
) -> dict:
    establishment, _membership = access
    return report_service.report_overview(db, establishment.id, start, end)


@router.get("/{establishment_id}/reports/sales-by-channel", response_model=list[SalesByChannel])
def sales_by_channel(
    start: datetime | None = None,
    end: datetime | None = None,
    access=Depends(admin_access),
    db: Session = Depends(get_db),
) -> list[dict]:
    establishment, _membership = access
    return report_service.sales_by_channel(db, establishment.id, start, end)


@router.get("/{establishment_id}/reports/top-products", response_model=list[TopProduct])
def top_products(
    start: datetime | None = None,
    end: datetime | None = None,
    access=Depends(admin_access),
    db: Session = Depends(get_db),
) -> list[dict]:
    establishment, _membership = access
    return report_service.top_products(db, establishment.id, start, end)


@router.get("/{establishment_id}/reports/profit-by-channel", response_model=list[ProfitByChannel])
def profit_by_channel(
    start: datetime | None = None,
    end: datetime | None = None,
    access=Depends(admin_access),
    db: Session = Depends(get_db),
) -> list[dict]:
    establishment, _membership = access
    return report_service.profit_by_channel(db, establishment.id, start, end)
