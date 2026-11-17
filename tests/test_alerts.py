from app.alerts import evaluate_transition


def test_falha_abaixo_do_limite_nao_alerta():
    t = evaluate_transition("up", 0, ok=False, threshold=3)
    assert t.event is None
    assert t.consecutive_failures == 1
    assert t.state == "up"


def test_terceira_falha_seguida_gera_alerta_de_queda():
    t = evaluate_transition("up", 2, ok=False, threshold=3)
    assert t.event == "down"
    assert t.state == "down"


def test_falhas_continuas_nao_repetem_alerta():
    t = evaluate_transition("down", 5, ok=False, threshold=3)
    assert t.event is None
    assert t.state == "down"


def test_recuperacao_gera_aviso():
    t = evaluate_transition("down", 6, ok=True, threshold=3)
    assert t.event == "recovered"
    assert t.state == "up"
    assert t.consecutive_failures == 0


def test_sucesso_normal_nao_gera_evento():
    t = evaluate_transition("up", 1, ok=True, threshold=3)
    assert t.event is None
    assert t.consecutive_failures == 0


def test_estado_desconhecido_vira_up_no_primeiro_sucesso():
    t = evaluate_transition("unknown", 0, ok=True, threshold=3)
    assert t.state == "up"
    assert t.event is None
