"""Integracoes da loja com marketplaces (iFood)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.deps import admin_access, staff_access
from app.db import get_db
from app.integrations.ifood import service as ifood_service
from app.integrations.ifood.client import IfoodError, get_ifood_client
from app.models.establishment import Establishment

router = APIRouter()


class IfoodStoreStatus(BaseModel):
    available: bool
    title: str
    subtitle: str | None = None


class IfoodIntegration(BaseModel):
    configured: bool
    polling: bool
    merchant_id: str | None = None
    merchant_name: str | None = None
    store_status: IfoodStoreStatus | None = None
    error: str | None = None


class IfoodLink(BaseModel):
    # merchantId da loja no iFood (vazio desconecta)
    merchant_id: str | None = Field(default=None, max_length=64)


class CancellationReason(BaseModel):
    code: str
    description: str


def _store_status(raw: list[dict]) -> IfoodStoreStatus | None:
    if not raw:
        return None
    first = raw[0]
    message = first.get("message") or {}
    return IfoodStoreStatus(
        available=bool(first.get("available")),
        title=message.get("title") or ("Loja aberta" if first.get("available") else "Loja fechada"),
        subtitle=(message.get("subtitle") or "").strip() or None,
    )


def _integration(establishment: Establishment) -> IfoodIntegration:
    settings = get_settings()
    client = get_ifood_client()
    result = IfoodIntegration(
        configured=client is not None,
        polling=client is not None and settings.ifood_polling_enabled,
        merchant_id=establishment.ifood_merchant_id,
    )
    if client is None or not establishment.ifood_merchant_id:
        return result
    try:
        merchants = {merchant["id"]: merchant.get("name") for merchant in client.merchants()}
        result.merchant_name = merchants.get(establishment.ifood_merchant_id)
        if result.merchant_name is None:
            result.error = "Esta loja do iFood nao autorizou o app (ou foi desvinculada no Portal do Parceiro)"
            return result
        result.store_status = _store_status(client.merchant_status(establishment.ifood_merchant_id))
    except IfoodError as exc:
        result.error = f"Nao foi possivel consultar o iFood: {exc}"
    return result


@router.get("/{establishment_id}/integrations/ifood", response_model=IfoodIntegration)
def ifood_integration(access=Depends(admin_access)) -> IfoodIntegration:
    establishment, _membership = access
    return _integration(establishment)


@router.put("/{establishment_id}/integrations/ifood", response_model=IfoodIntegration)
def link_ifood(payload: IfoodLink, access=Depends(admin_access), db: Session = Depends(get_db)) -> IfoodIntegration:
    """Liga esta loja a uma loja do iFood pelo ID (merchantId) dela.

    O ID e informado pelo dono (aparece no Portal do Parceiro); nao listamos as lojas do app para que um
    cliente do ComandaHub nao veja nem se ligue a loja de outro.
    """
    establishment, _membership = access
    merchant_id = (payload.merchant_id or "").strip() or None
    if merchant_id:
        client = ifood_service.require_client()
        try:
            authorized = {merchant["id"] for merchant in client.merchants()}
        except IfoodError as exc:
            raise HTTPException(status_code=502, detail=f"Nao foi possivel consultar o iFood: {exc}") from exc
        if merchant_id not in authorized:
            raise HTTPException(status_code=422, detail="Loja nao encontrada: confira o ID e se a loja autorizou o app no Portal do Parceiro do iFood")
        other = db.scalar(select(Establishment).where(Establishment.ifood_merchant_id == merchant_id, Establishment.id != establishment.id))
        if other is not None:
            raise HTTPException(status_code=409, detail="Esta loja do iFood ja esta ligada a outra loja do ComandaHub")
    establishment.ifood_merchant_id = merchant_id
    db.commit()
    db.refresh(establishment)
    return _integration(establishment)


@router.get("/{establishment_id}/orders/{order_id}/ifood/cancellation-reasons", response_model=list[CancellationReason])
def ifood_cancellation_reasons(order_id: str, access=Depends(staff_access), db: Session = Depends(get_db)) -> list[dict]:
    establishment, _membership = access
    order = ifood_service.get_ifood_order_or_404(db, establishment.id, order_id)
    return ifood_service.cancellation_reasons(order)
