import httpx

from app.checker import check_service


def _client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_resposta_200_e_ok():
    result = check_service("https://exemplo.com", 5, _client(lambda r: httpx.Response(200)))
    assert result.ok is True
    assert result.status_code == 200
    assert result.response_ms is not None


def test_resposta_500_e_falha():
    result = check_service("https://exemplo.com", 5, _client(lambda r: httpx.Response(500)))
    assert result.ok is False
    assert result.error == "HTTP 500"


def test_erro_de_conexao_e_falha():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("sem rota", request=request)

    result = check_service("https://exemplo.com", 5, _client(handler))
    assert result.ok is False
    assert result.status_code is None
    assert result.error == "ConnectError"
