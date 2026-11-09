"""Polling de eventos do iFood em segundo plano.

Roda dentro da API (uma thread) quando as credenciais estao configuradas. Alem de trazer os pedidos, o
polling e o "sinal de vida" que mantem a loja aberta no iFood: sem ele a loja aparece como fechada.
Com varias instancias da API, ligue o polling (IFOOD_POLLING_ENABLED) em apenas uma.
"""
from __future__ import annotations

import threading

import structlog
from sqlalchemy import select

import app.db as db_module
from app.integrations.ifood.client import IfoodClient
from app.integrations.ifood.service import process_events
from app.models.establishment import Establishment

logger = structlog.get_logger()


def poll_once(client: IfoodClient) -> int:
    """Um ciclo: busca eventos das lojas vinculadas, processa e confirma. Retorna quantos processou."""
    with db_module.SessionLocal() as db:
        merchant_ids = [mid for mid in db.scalars(select(Establishment.ifood_merchant_id).where(Establishment.ifood_merchant_id.is_not(None)))]
        if not merchant_ids:
            return 0
        events = client.poll_events(merchant_ids)
        if not events:
            return 0
        processed = process_events(db, client, events)
    client.acknowledge(processed)
    logger.info("ifood_events_processed", received=len(events), processed=len(processed))
    return len(processed)


class IfoodPoller:
    def __init__(self, client: IfoodClient, interval_seconds: int = 30) -> None:
        self._client = client
        self._interval = max(5, interval_seconds)
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="ifood-poller", daemon=True)

    def start(self) -> None:
        logger.info("ifood_poller_started", interval_seconds=self._interval)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._thread.join(timeout=10)

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                poll_once(self._client)
            except Exception:  # noqa: BLE001 - o polling nunca pode morrer
                logger.exception("ifood_poll_failed")
            self._stop.wait(self._interval)
