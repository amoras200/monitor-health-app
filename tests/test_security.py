import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.security import UnsafeURLError, validate_public_url, validate_url_for_registration

client = TestClient(app)
VALID_KEY = {"X-API-Key": "test-api-key-1234567890"}


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1",
        "http://localhost",
        "http://10.0.0.5",
        "http://192.168.1.10:8080",
        "http://169.254.169.254/latest/meta-data",
        "ftp://exemplo.com",
        "http://user:senha@8.8.8.8",
    ],
)
def test_urls_inseguras_sao_bloqueadas(url):
    with pytest.raises(UnsafeURLError):
        validate_public_url(url)


def test_ip_publico_e_aceito():
    validate_public_url("http://8.8.8.8")


def test_cadastro_aceita_hostname_sem_resolver_dns():
    validate_url_for_registration("https://example.com")


@pytest.mark.parametrize("url", ["http://localhost", "http://127.0.0.1", "http://10.0.0.5"])
def test_cadastro_bloqueia_alvos_internos_obvios(url):
    with pytest.raises(UnsafeURLError):
        validate_url_for_registration(url)


def test_health_nao_exige_chave():
    assert client.get("/health").status_code == 200


def test_sem_chave_retorna_401():
    assert client.get("/services").status_code == 401


def test_chave_errada_retorna_401():
    response = client.get("/services", headers={"X-API-Key": "chave-errada-123456789"})
    assert response.status_code == 401


def test_cadastro_de_url_interna_retorna_422():
    response = client.post(
        "/services", json={"name": "interno", "url": "http://127.0.0.1:8080"}, headers=VALID_KEY
    )
    assert response.status_code == 422
    assert "URL não permitida" in response.json()["detail"]


def test_cadastro_com_payload_invalido_retorna_422():
    response = client.post("/services", json={"name": "", "url": "nao-e-url"}, headers=VALID_KEY)
    assert response.status_code == 422
