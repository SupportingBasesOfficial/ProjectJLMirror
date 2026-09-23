"""Application configuration loaded from environment variables."""

from __future__ import annotations

from dataclasses import dataclass
import os


def _env(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


@dataclass(frozen=True)
class Settings:
    database_url: str
    database_migration_url: str
    api_host: str
    api_port: int
    environment_class: str
    session_secret: str
    oidc_issuer: str
    oidc_client_id: str
    oidc_client_secret: str
    oidc_redirect_uri: str
    worker_validation_interval: int
    worker_outbox_dispatch_interval: int
    worker_reconciliation_interval: int
    zabbix_api_token: str
    zabbix_credential_generation_ref: str

    @property
    def is_development(self) -> bool:
        return self.environment_class == "environment.development@1"


def load_settings() -> Settings:
    return Settings(
        database_url=_env("DATABASE_URL", "postgresql://jlmirror_app:app_password@localhost:5432/jlmirror"),
        database_migration_url=_env(
            "DATABASE_MIGRATION_URL",
            _env("DATABASE_URL", "postgresql://jlmirror:jlmirror@localhost:5432/jlmirror"),
        ),
        api_host=_env("API_HOST", "0.0.0.0"),
        api_port=int(_env("API_PORT", "8000")),
        environment_class=_env("ENVIRONMENT_CLASS", "environment.development@1"),
        session_secret=_env("SESSION_SECRET", "dev-only-not-for-production"),
        oidc_issuer=_env("OIDC_ISSUER", ""),
        oidc_client_id=_env("OIDC_CLIENT_ID", "jlmirror-bff"),
        oidc_client_secret=_env("OIDC_CLIENT_SECRET", ""),
        oidc_redirect_uri=_env("OIDC_REDIRECT_URI", "http://localhost:8000/auth/callback"),
        worker_validation_interval=int(_env("WORKER_VALIDATION_INTERVAL_SECONDS", "30")),
        worker_outbox_dispatch_interval=int(_env("WORKER_OUTBOX_DISPATCH_INTERVAL_SECONDS", "5")),
        worker_reconciliation_interval=int(_env("WORKER_RECONCILIATION_INTERVAL_SECONDS", "60")),
        zabbix_api_token=_env("ZABBIX_API_TOKEN", ""),
        zabbix_credential_generation_ref=_env("ZABBIX_CREDENTIAL_GENERATION_REF", "dev-cred-gen-1"),
    )


settings = load_settings()
