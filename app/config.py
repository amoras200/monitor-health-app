"""Configuração lida de variáveis de ambiente (nada de segredo no código)."""

import os
from dataclasses import dataclass
from functools import lru_cache

MIN_API_KEY_LENGTH = 16


def _bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    mongo_uri: str
    mongo_db: str
    api_key: str
    check_interval_seconds: int
    request_timeout_seconds: float
    failure_threshold: int
    retention_days: int
    max_workers: int
    allow_private_targets: bool
    smtp_host: str
    smtp_port: int
    smtp_user: str
    smtp_password: str
    smtp_from: str
    alert_to: str


@lru_cache
def get_settings() -> Settings:
    return Settings(
        mongo_uri=os.getenv("MONGO_URI", "mongodb://localhost:27017"),
        mongo_db=os.getenv("MONGO_DB", "healthmonitor"),
        api_key=os.getenv("API_KEY", ""),
        check_interval_seconds=int(os.getenv("CHECK_INTERVAL_SECONDS", "60")),
        request_timeout_seconds=float(os.getenv("REQUEST_TIMEOUT_SECONDS", "5")),
        failure_threshold=int(os.getenv("FAILURE_THRESHOLD", "3")),
        retention_days=int(os.getenv("RETENTION_DAYS", "7")),
        max_workers=int(os.getenv("MAX_WORKERS", "10")),
        allow_private_targets=_bool("ALLOW_PRIVATE_TARGETS", False),
        smtp_host=os.getenv("SMTP_HOST", ""),
        smtp_port=int(os.getenv("SMTP_PORT", "587")),
        smtp_user=os.getenv("SMTP_USER", ""),
        smtp_password=os.getenv("SMTP_PASSWORD", ""),
        smtp_from=os.getenv("SMTP_FROM", ""),
        alert_to=os.getenv("ALERT_TO", ""),
    )
