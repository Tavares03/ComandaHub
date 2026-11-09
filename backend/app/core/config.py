from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "ComandaHub"
    environment: str = "development"
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/comandahub"
    secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 720
    backend_cors_origins: str = "http://localhost:4200,http://localhost:8080,http://127.0.0.1:4200"
    log_level: str = "INFO"
    # Integracao iFood (app centralizado do Portal do Desenvolvedor). Vazio = integracao desligada.
    ifood_client_id: str = ""
    ifood_client_secret: str = ""
    ifood_api_url: str = "https://merchant-api.ifood.com.br"
    # Polling de eventos a cada 30 s (tambem mantem a loja aberta no iFood). Ligue em UMA instancia so.
    ifood_polling_enabled: bool = True
    ifood_polling_interval_seconds: int = 30

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.backend_cors_origins.split(",") if origin.strip()]

    @property
    def ifood_configured(self) -> bool:
        return bool(self.ifood_client_id.strip() and self.ifood_client_secret.strip())

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"

    def validate_for_runtime(self) -> None:
        # Valores de exemplo do repositorio (.env.example / docker-compose.yml) nunca valem em producao
        insecure = {
            "",
            "change-me-in-production",
            "change-this-demo-secret",
            "troque-esta-chave-por-uma-aleatoria-de-32-chars",
            "dev-only-secret-key-troque-em-producao-0123",
        }
        if self.is_production and (self.secret_key in insecure or len(self.secret_key) < 32):
            raise RuntimeError("Defina SECRET_KEY forte (32+ caracteres) antes de subir em producao.")


@lru_cache
def get_settings() -> Settings:
    return Settings()
