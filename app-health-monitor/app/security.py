"""Chave de API e validação de URLs (proteção contra SSRF)."""

import hmac
import ipaddress
import socket
from urllib.parse import urlparse

from fastapi import Header, HTTPException, status

from app.config import MIN_API_KEY_LENGTH, get_settings


class UnsafeURLError(ValueError):
    """URL não permitida para monitoramento."""


def validate_public_url(url: str, allow_private: bool = False) -> None:
    """Aceita só http/https apontando para endereços públicos.

    Impede que o monitor seja usado para acessar a rede interna
    (localhost, IPs privados, metadados de nuvem como 169.254.169.254).
    """
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise UnsafeURLError("use apenas http ou https")
    if parsed.username or parsed.password:
        raise UnsafeURLError("URLs com usuário e senha não são permitidas")
    host = parsed.hostname
    if not host:
        raise UnsafeURLError("URL sem host")

    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise UnsafeURLError("o host não resolve") from exc

    if allow_private:
        return
    for info in infos:
        ip = ipaddress.ip_address(info[4][0].split("%")[0])
        if not ip.is_global:
            raise UnsafeURLError("endereço interno ou reservado não é permitido")


def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    """Dependência do FastAPI: exige o cabeçalho X-API-Key."""
    expected = get_settings().api_key
    if len(expected) < MIN_API_KEY_LENGTH:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "API_KEY não configurada no servidor"
        )
    if not x_api_key or not hmac.compare_digest(x_api_key.encode(), expected.encode()):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "API key inválida ou ausente",
            headers={"WWW-Authenticate": "ApiKey"},
        )
