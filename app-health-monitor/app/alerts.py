"""Regra de transição de estado e envio de alertas por email."""

import logging
import smtplib
import ssl
from dataclasses import dataclass
from email.message import EmailMessage

from app.config import Settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Transition:
    state: str  # "up", "down" ou "unknown"
    consecutive_failures: int
    event: str | None  # "down", "recovered" ou None


def evaluate_transition(
    previous_state: str, consecutive_failures: int, ok: bool, threshold: int
) -> Transition:
    """Decide se uma checagem gera alerta.

    O alerta só sai na MUDANÇA de estado: cai depois de N falhas seguidas
    e avisa quando volta. Isso evita enviar um email a cada checagem.
    """
    if ok:
        event = "recovered" if previous_state == "down" else None
        return Transition("up", 0, event)

    failures = consecutive_failures + 1
    if failures >= threshold and previous_state != "down":
        return Transition("down", failures, "down")
    state = previous_state if previous_state in {"up", "down"} else "unknown"
    return Transition(state, failures, None)


def send_alert(settings: Settings, name: str, url: str, event: str, detail: str) -> None:
    if event == "down":
        subject = f"[ALERTA] {name} fora do ar"
        body = f"O serviço {name} ({url}) falhou {settings.failure_threshold} vezes seguidas.\n"
    else:
        subject = f"[OK] {name} voltou"
        body = f"O serviço {name} ({url}) voltou a responder.\n"
    body += f"Detalhe: {detail}\n"

    if not (settings.smtp_host and settings.alert_to and settings.smtp_from):
        logger.warning("SMTP não configurado. Alerta apenas no log: %s | %s", subject, detail)
        return

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = settings.smtp_from
    message["To"] = settings.alert_to
    message.set_content(body)

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
            smtp.starttls(context=ssl.create_default_context())
            if settings.smtp_user:
                smtp.login(settings.smtp_user, settings.smtp_password)
            smtp.send_message(message)
        logger.info("Alerta enviado: %s", subject)
    except (smtplib.SMTPException, OSError):
        logger.exception("Falha ao enviar o alerta: %s", subject)
