"""Cliente HTTP da Merchant API do iFood (app centralizado, grant client_credentials)."""
from __future__ import annotations

import threading
import time
from typing import Any

import httpx
import structlog

from app.core.config import get_settings

logger = structlog.get_logger()

# Renova o token um pouco antes de vencer (o iFood entrega validade de ~6 h)
TOKEN_SAFETY_SECONDS = 300


class IfoodError(Exception):
    """Falha ao falar com o iFood (rede, credencial ou recusa da acao)."""

    def __init__(self, message: str, status_code: int | None = None, body: Any = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.body = body


class IfoodClient:
    def __init__(self, client_id: str, client_secret: str, base_url: str, timeout: float = 20.0,
                 transport: httpx.BaseTransport | None = None) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._http = httpx.Client(base_url=base_url, timeout=timeout, transport=transport)
        self._token: str | None = None
        self._token_expires_at = 0.0
        self._lock = threading.Lock()

    # ------------------------------------------------------------------ autenticacao

    def _access_token(self) -> str:
        with self._lock:
            if self._token and time.monotonic() < self._token_expires_at:
                return self._token
            try:
                response = self._http.post(
                    "/authentication/v1.0/oauth/token",
                    data={"grantType": "client_credentials", "clientId": self._client_id, "clientSecret": self._client_secret},
                )
            except httpx.HTTPError as exc:
                raise IfoodError(f"Sem conexao com o iFood: {exc}") from exc
            if response.status_code != 200:
                raise IfoodError("Credenciais do iFood recusadas (confira IFOOD_CLIENT_ID e IFOOD_CLIENT_SECRET)",
                                 response.status_code, _body(response))
            payload = response.json()
            self._token = payload["accessToken"]
            self._token_expires_at = time.monotonic() + max(60, int(payload.get("expiresIn", 3600)) - TOKEN_SAFETY_SECONDS)
            return self._token

    def _request(self, method: str, path: str, *, expected: tuple[int, ...] = (200,), **kwargs) -> httpx.Response:
        headers = {"Authorization": f"Bearer {self._access_token()}", **kwargs.pop("headers", {})}
        try:
            response = self._http.request(method, path, headers=headers, **kwargs)
        except httpx.HTTPError as exc:
            raise IfoodError(f"Sem conexao com o iFood: {exc}") from exc
        if response.status_code == 401:
            # Token revogado/expirado antes da hora: renova uma vez
            with self._lock:
                self._token = None
            headers["Authorization"] = f"Bearer {self._access_token()}"
            response = self._http.request(method, path, headers=headers, **kwargs)
        if response.status_code not in expected:
            body = _body(response)
            raise IfoodError(_message(body) or f"iFood respondeu HTTP {response.status_code}", response.status_code, body)
        return response

    # ------------------------------------------------------------------ lojas

    def merchants(self) -> list[dict]:
        """Lojas que autorizaram este app."""
        return self._request("GET", "/merchant/v1.0/merchants").json()

    def merchant_status(self, merchant_id: str) -> list[dict]:
        return self._request("GET", f"/merchant/v1.0/merchants/{merchant_id}/status").json()

    # ------------------------------------------------------------------ eventos

    def poll_events(self, merchant_ids: list[str]) -> list[dict]:
        """Eventos novos das lojas (204 = nenhum). Tambem e o "sinal de vida" que deixa a loja aberta."""
        headers = {"x-polling-merchants": ",".join(merchant_ids)} if merchant_ids else {}
        response = self._request("GET", "/events/v1.0/events:polling", expected=(200, 204), headers=headers)
        return response.json() if response.status_code == 200 and response.content else []

    def acknowledge(self, event_ids: list[str]) -> None:
        if event_ids:
            self._request("POST", "/events/v1.0/events/acknowledgment", expected=(200, 202, 204),
                          json=[{"id": event_id} for event_id in event_ids])

    # ------------------------------------------------------------------ pedidos

    def order(self, order_id: str) -> dict:
        return self._request("GET", f"/order/v1.0/orders/{order_id}").json()

    def confirm(self, order_id: str) -> None:
        self._request("POST", f"/order/v1.0/orders/{order_id}/confirm", expected=(200, 202))

    def start_preparation(self, order_id: str) -> None:
        self._request("POST", f"/order/v1.0/orders/{order_id}/startPreparation", expected=(200, 202))

    def ready_to_pickup(self, order_id: str) -> None:
        self._request("POST", f"/order/v1.0/orders/{order_id}/readyToPickup", expected=(200, 202))

    def dispatch(self, order_id: str) -> None:
        self._request("POST", f"/order/v1.0/orders/{order_id}/dispatch", expected=(200, 202))

    def cancellation_reasons(self, order_id: str) -> list[dict]:
        response = self._request("GET", f"/order/v1.0/orders/{order_id}/cancellationReasons", expected=(200, 204))
        return response.json() if response.status_code == 200 and response.content else []

    def request_cancellation(self, order_id: str, code: str, reason: str) -> None:
        self._request("POST", f"/order/v1.0/orders/{order_id}/requestCancellation", expected=(200, 202),
                      json={"cancellationCode": code, "reason": reason})


def _body(response: httpx.Response) -> Any:
    try:
        return response.json()
    except ValueError:
        return response.text[:500]


def _message(body: Any) -> str | None:
    if isinstance(body, dict):
        error = body.get("error") if isinstance(body.get("error"), dict) else body
        for key in ("message", "description", "detail"):
            if isinstance(error.get(key), str):
                return error[key]
    return None


_client: IfoodClient | None = None
_client_lock = threading.Lock()


def get_ifood_client() -> IfoodClient | None:
    """Cliente compartilhado (None quando as credenciais nao estao configuradas)."""
    global _client
    settings = get_settings()
    if not settings.ifood_configured:
        return None
    with _client_lock:
        if _client is None:
            _client = IfoodClient(settings.ifood_client_id.strip(), settings.ifood_client_secret.strip(), settings.ifood_api_url)
        return _client
