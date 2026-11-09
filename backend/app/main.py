from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

from app.api.router import api_router
from app.core.config import get_settings
from app.core.logging import configure_logging

settings = get_settings()
configure_logging(settings.log_level)
settings.validate_for_runtime()

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    poller = None
    if settings.ifood_polling_enabled:
        from app.integrations.ifood.client import get_ifood_client
        from app.integrations.ifood.poller import IfoodPoller

        client = get_ifood_client()
        if client is not None:
            poller = IfoodPoller(client, settings.ifood_polling_interval_seconds)
            poller.start()
    yield
    if poller is not None:
        poller.stop()


app = FastAPI(
    lifespan=lifespan,
    title=settings.app_name,
    version="1.0.0",
    description=(
        "API do ComandaHub: central de pedidos multi-loja para restaurantes (iFood, 99Food, delivery proprio, "
        "retirada e balcao), com cozinha, caixa, estoque, clientes, relatorios e cardapio online. "
        "Autentique em `POST /api/v1/auth/login` e use o token no botao **Authorize**."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(IntegrityError)
async def integrity_error_handler(_request: Request, exc: IntegrityError) -> JSONResponse:
    # Ex.: produto/categoria/loja com nome repetido. Sem isso o cliente recebia um 500 generico.
    logger.warning("integrity_error", error=str(exc.orig)[:300])
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"detail": "Ja existe um registro com esses dados (nome duplicado ou conflito)."},
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(api_router)
