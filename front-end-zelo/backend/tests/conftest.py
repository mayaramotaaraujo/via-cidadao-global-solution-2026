"""Fixtures: API com LLM, clima e banco controlados (sem internet, sem custo)."""

import os

os.environ.setdefault("LLM_PROVIDER", "fake")
os.environ.setdefault("SEED_DEMO", "false")
os.environ.setdefault("GESTOR_TOKEN", "token-de-teste")

import pytest
from fastapi.testclient import TestClient

from app.core.dependencias import limitar_analises, obter_clima, obter_llm, obter_repositorio
from app.main import app
from app.providers.llm import FakeProvedor
from app.providers.repositorio import Repositorio
from app.schemas.relato import AnaliseLLM, Categoria, ContextoClima, Urgencia


class LLMEspiao(FakeProvedor):
    """Provedor falso que registra o que foi enviado e pode simular falhas."""

    def __init__(self):
        self.ultimo_conteudo: str | None = None
        self.erro: Exception | None = None
        self.resposta: AnaliseLLM | None = None

    def analisar(self, instrucoes, conteudo):
        self.ultimo_conteudo = conteudo
        if self.erro:
            raise self.erro
        return self.resposta or super().analisar(instrucoes, conteudo)


class ClimaFixo:
    def __init__(self, mm: float | None = None):
        self.mm = mm

    def previsao_hoje(self, lat, lon):
        return None if self.mm is None else ContextoClima(chuva_prevista_mm=self.mm, probabilidade_chuva=90)


@pytest.fixture
def llm():
    return LLMEspiao()


@pytest.fixture
def clima():
    return ClimaFixo()


@pytest.fixture
def cliente(llm, clima):
    repo = Repositorio(":memory:")
    app.dependency_overrides[obter_llm] = lambda: llm
    app.dependency_overrides[obter_clima] = lambda: clima
    app.dependency_overrides[obter_repositorio] = lambda: repo
    app.dependency_overrides[limitar_analises] = lambda: None
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    app.dependency_overrides.clear()


def analise_llm(**kw) -> AnaliseLLM:
    base = dict(
        categoria=Categoria.BURACO,
        urgencia=Urgencia.MEDIA,
        justificativa_urgencia="ok",
        resumo="Buraco na rua",
        orientacoes_cidadao=["a", "b"],
        risco_imediato=False,
        fora_do_escopo=False,
        confianca=0.9,
    )
    base.update(kw)
    return AnaliseLLM(**base)


RELATO_VALIDO = {
    "descricao": "Tem um buraco enorme na rua em frente à escola, carros desviando",
    "bairro": "Mooca",
    "referencia": "Em frente à EMEF",
}
