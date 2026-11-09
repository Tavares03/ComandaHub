"""Limite de tentativas em memoria (janela deslizante por chave).

Protege login (forca bruta) e o cardapio publico (spam de pedidos e de cupons). Vale por processo:
com varios workers/instancias cada um conta separado; para escalar horizontalmente troque por um
contador compartilhado (ex.: Redis).
"""
from __future__ import annotations

import time
from collections import deque
from threading import Lock

from fastapi import HTTPException, Request, status


class RateLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = {}
        self._lock = Lock()

    def _recent(self, key: str, window: float, now: float) -> deque[float]:
        hits = self._hits.get(key)
        if hits is None:
            hits = self._hits[key] = deque()
        while hits and now - hits[0] >= window:
            hits.popleft()
        return hits

    def allowed(self, key: str, limit: int, window: float) -> bool:
        """Ainda cabe mais uma tentativa? (nao registra nada)"""
        with self._lock:
            hits = self._recent(key, window, time.monotonic())
            allowed = len(hits) < limit
            if not hits:
                self._hits.pop(key, None)
            return allowed

    def hit(self, key: str, limit: int, window: float) -> bool:
        """Registra uma tentativa. Retorna False se ja passou do limite (e nao registra)."""
        with self._lock:
            now = time.monotonic()
            hits = self._recent(key, window, now)
            if len(hits) >= limit:
                return False
            hits.append(now)
            return True

    def reset(self, key: str | None = None) -> None:
        with self._lock:
            if key is None:
                self._hits.clear()
            else:
                self._hits.pop(key, None)


limiter = RateLimiter()


def client_ip(request: Request) -> str:
    # Atras de proxy (nginx), rode o uvicorn com --proxy-headers para request.client ser o IP real.
    return request.client.host if request.client else "unknown"


def too_many(window: float, message: str = "Muitas tentativas. Aguarde alguns minutos e tente de novo.") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail=message,
        headers={"Retry-After": str(int(window))},
    )


def enforce(key: str, limit: int, window: float, message: str | None = None) -> None:
    """Registra a tentativa ou responde 429."""
    if not limiter.hit(key, limit, window):
        raise too_many(window, message) if message else too_many(window)
