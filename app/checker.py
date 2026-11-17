"""Worker que verifica os serviços cadastrados e grava o resultado no MongoDB."""

import logging
import signal
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime

import httpx
from pymongo.database import Database
from pymongo.errors import PyMongoError

from app.alerts import evaluate_transition, send_alert
from app.config import Settings, get_settings
from app.db import ensure_indexes, get_db
from app.security import UnsafeURLError, validate_public_url

logger = logging.getLogger("checker")


@dataclass(frozen=True)
class CheckResult:
    ok: bool
    status_code: int | None
    response_ms: int | None
    error: str | None


def check_service(url: str, timeout: float, client: httpx.Client | None = None) -> CheckResult:
    """Faz um GET e mede o tempo. Não segue redirecionamentos (evita desvio para IP interno)."""
    owns_client = client is None
    client = client or httpx.Client(
        timeout=timeout,
        follow_redirects=False,
        headers={"User-Agent": "app-health-monitor/0.1"},
    )
    started = time.perf_counter()
    try:
        with client.stream("GET", url) as response:  # não baixa o corpo da resposta
            elapsed = round((time.perf_counter() - started) * 1000)
            ok = 200 <= response.status_code < 400
            error = None if ok else f"HTTP {response.status_code}"
            return CheckResult(ok, response.status_code, elapsed, error)
    except httpx.HTTPError as exc:
        elapsed = round((time.perf_counter() - started) * 1000)
        return CheckResult(False, None, elapsed, type(exc).__name__)
    finally:
        if owns_client:
            client.close()


def process_service(db: Database, service: dict, settings: Settings) -> None:
    try:
        validate_public_url(service["url"], settings.allow_private_targets)
    except UnsafeURLError as exc:
        result = CheckResult(False, None, None, f"URL bloqueada: {exc}")
    else:
        result = check_service(service["url"], settings.request_timeout_seconds)

    now = datetime.now(UTC)
    db.checks.insert_one(
        {
            "service_id": service["_id"],
            "ts": now,
            "ok": result.ok,
            "status_code": result.status_code,
            "response_ms": result.response_ms,
            "error": result.error,
        }
    )

    transition = evaluate_transition(
        service.get("state", "unknown"),
        service.get("consecutive_failures", 0),
        result.ok,
        settings.failure_threshold,
    )
    db.services.update_one(
        {"_id": service["_id"]},
        {
            "$set": {
                "state": transition.state,
                "consecutive_failures": transition.consecutive_failures,
                "last_check_at": now,
            }
        },
    )
    if transition.event:
        detail = result.error or "respondeu normalmente"
        send_alert(settings, service["name"], service["url"], transition.event, detail)


def _safe_process(db: Database, service: dict, settings: Settings) -> None:
    try:
        process_service(db, service, settings)
    except Exception:  # um serviço com problema não pode derrubar o ciclo
        logger.exception("Erro ao processar %s", service.get("url"))


def run_cycle(db: Database, settings: Settings) -> None:
    services = list(db.services.find({}))
    if not services:
        return
    with ThreadPoolExecutor(max_workers=settings.max_workers) as pool:
        for service in services:
            pool.submit(_safe_process, db, service, settings)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    settings = get_settings()
    stop = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    signal.signal(signal.SIGINT, lambda *_: stop.set())

    db = get_db()
    logger.info("Worker iniciado (intervalo: %ss)", settings.check_interval_seconds)
    indexes_ready = False
    while not stop.is_set():
        try:
            if not indexes_ready:
                ensure_indexes(db)
                indexes_ready = True
            run_cycle(db, settings)
        except PyMongoError:
            logger.exception("Erro de banco de dados; tentando de novo no próximo ciclo")
        stop.wait(settings.check_interval_seconds)
    logger.info("Worker encerrado")


if __name__ == "__main__":
    main()
