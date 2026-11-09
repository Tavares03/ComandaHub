"""Regras da integracao iFood: eventos (iFood -> ComandaHub) e mudancas de status (ComandaHub -> iFood)."""
from __future__ import annotations

import structlog
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.integrations.ifood.client import IfoodClient, IfoodError, get_ifood_client
from app.integrations.ifood.mapper import parse_order
from app.models.establishment import Establishment
from app.models.order import FulfillmentType, Order, OrderSource, OrderStatus
from app.services.order_service import add_event, apply_marketplace_status, create_marketplace_order, get_order_or_404

logger = structlog.get_logger()

INTEGRATION = "IFOOD"

# Evento do iFood (fullCode ou code curto) -> status no ComandaHub
STATUS_BY_EVENT = {
    "CONFIRMED": OrderStatus.ACCEPTED, "CFM": OrderStatus.ACCEPTED,
    "PREPARATION_STARTED": OrderStatus.PREPARING, "PRS": OrderStatus.PREPARING,
    "READY_TO_PICKUP": OrderStatus.READY, "RTP": OrderStatus.READY,
    "DISPATCHED": OrderStatus.OUT_FOR_DELIVERY, "DSP": OrderStatus.OUT_FOR_DELIVERY,
    "CONCLUDED": OrderStatus.FINISHED, "CON": OrderStatus.FINISHED,
    "CANCELLED": OrderStatus.CANCELED, "CAN": OrderStatus.CANCELED,
}
PLACED = {"PLACED", "PLC"}
# Eventos de pedido ja encerrado: se o pedido nao existe aqui, nao vale a pena importar
CLOSING = {"CONCLUDED", "CON", "CANCELLED", "CAN"}


def _codes(event: dict) -> tuple[str, str]:
    return str(event.get("fullCode") or "").upper(), str(event.get("code") or "").upper()


def _find_order(db: Session, external_id: str) -> Order | None:
    return db.scalar(select(Order).where(Order.source == OrderSource.IFOOD, Order.external_order_id == external_id))


def import_order(db: Session, client: IfoodClient, establishment: Establishment, external_id: str) -> Order:
    raw = client.order(external_id)
    data = parse_order(raw, establishment.timezone)
    return create_marketplace_order(db, establishment.id, data, OrderSource.IFOOD, INTEGRATION, raw_payload=raw)


def handle_event(db: Session, client: IfoodClient, event: dict) -> None:
    full_code, code = _codes(event)
    external_id = event.get("orderId")
    if not external_id:
        return  # eventos sem pedido (ex.: da loja) nao mudam nada aqui
    establishment = db.scalar(select(Establishment).where(Establishment.ifood_merchant_id == event.get("merchantId")))
    if establishment is None:
        logger.warning("ifood_event_unlinked_merchant", merchant_id=event.get("merchantId"), code=full_code or code)
        return

    order = _find_order(db, external_id)
    if order is None:
        if full_code in CLOSING or code in CLOSING:
            return
        # PLACED, ou um evento de pedido que chegou antes/sem o PLACED: importa do iFood
        order = import_order(db, client, establishment, external_id)
        logger.info("ifood_order_imported", order_number=order.order_number, display_id=order.external_display_id)
        if full_code in PLACED or code in PLACED:
            return

    new_status = STATUS_BY_EVENT.get(full_code) or STATUS_BY_EVENT.get(code)
    if new_status is not None:
        apply_marketplace_status(db, order, new_status, {"ifood_event": full_code or code})
    elif full_code not in PLACED and code not in PLACED:
        # Ex.: entregador a caminho, coleta, pedido de cancelamento do cliente: fica no historico do pedido
        add_event(db, order, f"IFOOD_{full_code or code}", None, None, {"metadata": event.get("metadata") or {}})
    db.commit()


def process_events(db: Session, client: IfoodClient, events: list[dict]) -> list[str]:
    """Processa e devolve os ids que podem ser confirmados (ack). Falhas ficam para o proximo polling."""
    processed: list[str] = []
    for event in events:
        try:
            handle_event(db, client, event)
            processed.append(event["id"])
        except Exception:  # noqa: BLE001 - um evento ruim nao pode parar os outros
            db.rollback()
            logger.exception("ifood_event_failed", event_id=event.get("id"), code=event.get("fullCode") or event.get("code"))
    return processed


def require_client() -> IfoodClient:
    client = get_ifood_client()
    if client is None:
        raise HTTPException(status_code=503, detail="Integracao com o iFood nao configurada (defina IFOOD_CLIENT_ID e IFOOD_CLIENT_SECRET)")
    return client


def push_status(db: Session, order: Order, new_status: OrderStatus, cancel_code: str | None, cancel_reason: str | None) -> bool:
    """Avisa o iFood da mudanca feita no ComandaHub.

    Retorna True quando a mudanca local deve esperar o iFood (cancelamento: so muda com o evento CANCELLED).
    """
    client = require_client()
    external_id = order.external_order_id
    try:
        if new_status == OrderStatus.ACCEPTED:
            client.confirm(external_id)
        elif new_status == OrderStatus.PREPARING:
            try:
                client.start_preparation(external_id)
            except IfoodError as exc:
                # Inicio de preparo e informativo no iFood: nao trava a cozinha
                add_event(db, order, "IFOOD_SYNC_WARNING", None, None, {"action": "startPreparation", "error": str(exc)})
        elif new_status == OrderStatus.READY:
            if order.marketplace_delivery or order.fulfillment_type != FulfillmentType.DELIVERY:
                client.ready_to_pickup(external_id)
        elif new_status == OrderStatus.OUT_FOR_DELIVERY:
            client.dispatch(external_id)
        elif new_status == OrderStatus.CANCELED:
            if not (cancel_code or "").strip():
                raise HTTPException(status_code=422, detail="Escolha o motivo de cancelamento do iFood")
            client.request_cancellation(external_id, cancel_code.strip(), (cancel_reason or "").strip())
            add_event(db, order, "IFOOD_CANCELLATION_REQUESTED", None, None, {"code": cancel_code, "reason": cancel_reason})
            return True
    except IfoodError as exc:
        logger.warning("ifood_push_failed", order_id=order.id, status=new_status.value, error=str(exc), http=exc.status_code)
        raise HTTPException(status_code=502, detail=f"O iFood recusou: {exc}") from exc
    return False


def cancellation_reasons(order: Order) -> list[dict]:
    client = require_client()
    try:
        reasons = client.cancellation_reasons(order.external_order_id)
    except IfoodError as exc:
        raise HTTPException(status_code=502, detail=f"Nao foi possivel buscar os motivos no iFood: {exc}") from exc
    return [
        {"code": str(reason.get("cancelCodeId") or reason.get("code")), "description": reason.get("description") or ""}
        for reason in reasons
        if reason.get("cancelCodeId") or reason.get("code")
    ]


def get_ifood_order_or_404(db: Session, establishment_id: str, order_id: str) -> Order:
    order = get_order_or_404(db, establishment_id, order_id)
    if order.integration != INTEGRATION:
        raise HTTPException(status_code=422, detail="Este pedido nao veio do iFood")
    return order
