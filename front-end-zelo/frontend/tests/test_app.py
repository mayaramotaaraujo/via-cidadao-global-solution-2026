"""Testes da interface com streamlit.testing (rodam sem navegador e sem back-end)."""

import os
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parents[1] / "app.py")


@pytest.fixture
def app_sem_api(monkeypatch):
    # Porta onde nada escuta: simula "API fora do ar".
    monkeypatch.setenv("API_URL", "http://127.0.0.1:9")
    import config, importlib
    importlib.reload(config)
    from providers import api_client
    api_client.obter_cliente.clear()
    api_client.carregar_bairros.clear()
    api_client.carregar_relatos_publicos.clear()
    api_client._saude_ok.clear()
    return AppTest.from_file(APP, default_timeout=20)


def test_app_abre_sem_excecao_mesmo_com_api_fora(app_sem_api):
    at = app_sem_api.run()
    assert not at.exception
    textos = " ".join(m.value for m in at.markdown)
    assert "Serviço indisponível" in textos


def test_api_fora_mostra_mensagem_amigavel_sem_detalhe_tecnico(app_sem_api):
    at = app_sem_api.run()
    erros = " ".join(e.value for e in at.error)
    assert "Não conseguimos falar com o serviço" in erros
    assert "Traceback" not in erros and "ConnectError" not in erros


def test_validacao_no_front_antes_de_chamar_a_api():
    from features.relatar import validar_entrada

    erros = validar_entrada("buraco", None, "", False)
    assert set(erros) == {"Descrição", "Bairro", "Privacidade"}
    assert validar_entrada("Tem um buraco enorme na rua da escola", "Mooca", "", True) == {}
    assert "Ponto de referência" in validar_entrada("Tem um buraco enorme na rua", "Mooca", "x" * 151, True)


def test_api_acordando_mostra_mensagem_de_inicio_e_nao_erro_generico():
    """A plataforma devolve HTML com 503 enquanto a API sai da hibernação."""
    import httpx

    from providers.api_client import ClienteZelo, ErroAPI

    def resposta(_):
        return httpx.Response(503, text="<html>Service Unavailable</html>", headers={"content-type": "text/html"})

    cliente = ClienteZelo("http://api.teste")
    cliente._http = httpx.Client(base_url="http://api.teste", transport=httpx.MockTransport(resposta))
    with pytest.raises(ErroAPI) as exc:
        cliente.bairros()
    assert exc.value.codigo == "API_INICIANDO"
    assert "iniciando" in exc.value.mensagem
    assert "<html" not in exc.value.mensagem


def _analise_fora_do_escopo(risco_imediato: bool) -> dict:
    return {
        "analise_id": "a1", "resumo": "Ônibus não está parando no ponto.", "categoria": "outros",
        "urgencia": "baixa", "justificativa_urgencia": "Sem dano urbano.", "orgao_responsavel": "Central SP156",
        "prazo_estimado_dias": 30, "orientacoes_cidadao": ["Registre no 156."], "risco_imediato": risco_imediato,
        "fora_do_escopo": True, "precisa_revisao_humana": True, "motivos_revisao": ["Fora do escopo."],
        "dados_pessoais_removidos": [], "contexto_clima": None, "ajustes_por_regra": [],
    }


def _abrir_revisao(app_sem_api, analise: dict) -> AppTest:
    at = app_sem_api.run()
    at.session_state["analise_atual"] = analise
    at.session_state["entrada_atual"] = {"descricao": "texto", "bairro": "Mooca", "referencia": None}
    at.session_state["etapa"] = "revisao"
    return at.run()


def test_fora_do_escopo_explica_bloqueio_e_esconde_prazo(app_sem_api):
    at = _abrir_revisao(app_sem_api, _analise_fora_do_escopo(risco_imediato=False))
    assert not at.exception
    avisos = " ".join(w.value for w in at.warning)
    assert "156" in avisos and "190" not in avisos          # sem aviso de emergência fora de contexto
    textos = " ".join(m.value for m in at.markdown) + " ".join(c.value for c in at.caption)
    assert "Prazo de referência" not in textos              # não promete reparo
    assert "O que fazer agora" in textos
    assert "desativado" in textos                           # explica por que o botão está bloqueado
    confirmar = next(b for b in at.button if b.label == "Confirmar e gerar protocolo")
    assert confirmar.disabled


def test_fora_do_escopo_com_risco_mantem_telefones_de_emergencia(app_sem_api):
    at = _abrir_revisao(app_sem_api, _analise_fora_do_escopo(risco_imediato=True))
    assert "190" in " ".join(w.value for w in at.warning)


def test_aguardar_servico_espera_a_api_acordar():
    """Primeiro a plataforma devolve 503 (API acordando); depois responde ok."""
    import httpx

    from providers import api_client

    chamadas = {"n": 0}

    def resposta(_):
        chamadas["n"] += 1
        if chamadas["n"] < 3:
            return httpx.Response(503, text="<html>acordando</html>", headers={"content-type": "text/html"})
        return httpx.Response(200, json={"status": "ok"})

    cliente = api_client.ClienteZelo("http://api.teste")
    cliente._http = httpx.Client(base_url="http://api.teste", transport=httpx.MockTransport(resposta))
    original = api_client.obter_cliente
    api_client.obter_cliente = lambda: cliente
    try:
        assert api_client.aguardar_servico(limite_s=5, pausa_s=0) is True
    finally:
        api_client.obter_cliente = original
    assert chamadas["n"] == 3


def test_aguardar_servico_desiste_na_hora_se_conexao_recusada(app_sem_api):
    import time

    from providers import api_client

    inicio = time.monotonic()
    assert api_client.aguardar_servico(limite_s=60) is False
    assert time.monotonic() - inicio < 5
