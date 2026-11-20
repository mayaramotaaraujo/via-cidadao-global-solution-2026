"""Testes automatizados (pytest). Rodar com: python -m pytest -q"""

from __future__ import annotations

import pandas as pd
import pytest

from scripts.gerar_dados import gerar_lote_demo
from scripts.servidores_teste import HTTPLocal
from zelo_robo import ingestao, integracoes
from zelo_robo.banco import Banco
from zelo_robo.config import Config
from zelo_robo.privacidade import anonimizar, mascarar_email
from zelo_robo.referencia import email_do_orgao, normalizar_bairro, orgao_para
from zelo_robo.regras import calcular_urgencia, decidir
from zelo_robo.robo import executar


@pytest.fixture
def cfg(tmp_path):
    c = Config.carregar()
    c.pasta_entrada, c.pasta_saida, c.pasta_logs = tmp_path / "entrada", tmp_path / "saida", tmp_path / "logs"
    c.caminho_banco = tmp_path / "robo.db"
    c.zelo_api_url = c.zelo_gestor_token = ""
    c.email_modo, c.clima_habilitado, c.espera_retry_s, c.nivel_log_console = "arquivo", False, 0, 100
    return c


# --- privacidade ---------------------------------------------------------------
def test_anonimiza_cpf_telefone_email_e_placa():
    texto, removidos = anonimizar("CPF 123.456.789-00, fone (11) 98765-4321, a@b.com, carro ABC1D23")
    assert "123.456" not in texto and "98765" not in texto and "a@b.com" not in texto and "ABC1D23" not in texto
    assert set(removidos) == {"CPF", "telefone", "e-mail", "placa"}


def test_nao_confunde_data_com_telefone():
    assert anonimizar("execução 20261118-140304")[1] == []


def test_mascara_email_no_log():
    assert mascarar_email("maria.silva@example.com") == "m***@example.com"


# --- referência ---------------------------------------------------------------
def test_normaliza_bairro_sem_acento_e_caixa_alta():
    assert normalizar_bairro("SAO MIGUEL  paulista") == "São Miguel Paulista"
    assert normalizar_bairro("Bairro Inventado") is None


def test_orgao_e_email_por_subprefeitura():
    assert orgao_para("buraco_pavimentacao", "Capão Redondo") == "Subprefeitura Campo Limpo"
    assert orgao_para("iluminacao_publica", "Sé").startswith("ILUME")
    assert email_do_orgao("Subprefeitura Santana/Tucuruvi") == "zeladoria.santana.tucuruvi@example.com"


# --- ingestão (Pandas) ------------------------------------------------------------
def test_validacao_manda_linhas_ruins_para_quarentena():
    df = pd.DataFrame([
        {"canal": "sp156", "id_origem": "1", "recebido_em": pd.Timestamp("2026-11-18"), "bairro": "PENHA",
         "descricao": "Buraco grande na rua principal do bairro", "email_cidadao": "x@example.com", "consentimento": "S"},
        {"canal": "sp156", "id_origem": "2", "recebido_em": pd.Timestamp("2026-11-18"), "bairro": "Atlântida",
         "descricao": "Poste apagado na esquina da padaria", "email_cidadao": "", "consentimento": "N"},
        {"canal": "sp156", "id_origem": "3", "recebido_em": pd.NaT, "bairro": "Lapa",
         "descricao": "Lixo acumulado na praça há dias", "email_cidadao": "", "consentimento": "N"},
    ])
    ok, quarentena, dup = ingestao.validar(df)
    assert len(ok) == 1 and ok.loc[0, "bairro"] == "Penha"
    assert set(quarentena["motivo"]) == {"bairro não reconhecido", "data de abertura inválida"}


def test_email_sem_consentimento_e_descartado():
    df = pd.DataFrame([{"canal": "sp156", "id_origem": "9", "recebido_em": pd.Timestamp("2026-11-18"),
                        "bairro": "Lapa", "descricao": "Árvore precisando de poda urgente",
                        "email_cidadao": "y@example.com", "consentimento": "N"}])
    ok, _, _ = ingestao.validar(df)
    assert ok.loc[0, "email_cidadao"] == ""


# --- regras --------------------------------------------------------------------
@pytest.mark.parametrize("texto,categoria,esperado", [
    ("Fio do poste caído soltando faísca", "iluminacao_publica", "critica"),
    ("Calçada quebrada, cadeirante não passa", "calcada_acessibilidade", "alta"),
    ("Lixo acumulado na esquina", "lixo_entulho", "media"),
    ("Pequeno buraco, não é urgente", "buraco_pavimentacao", "baixa"),
])
def test_urgencia(texto, categoria, esperado):
    assert calcular_urgencia(texto, categoria, None)[0] == esperado


def test_chuva_forte_sobe_urgencia_de_alagamento():
    sem, _ = calcular_urgencia("Bueiro entupido de folhas", "alagamento_drenagem", 0.0)
    com, motivos = calcular_urgencia("Bueiro entupido de folhas", "alagamento_drenagem", 35.0)
    assert (sem, com) == ("media", "alta") and "mm de chuva" in motivos[-1]


def test_baixa_confianca_vai_para_revisao():
    d = decidir("algo estranho na rua", "Lapa", "buraco_pavimentacao", 0.3, None, 0.55)
    assert d.precisa_revisao and "confiança" in d.motivos_revisao[0]


# --- integrações -----------------------------------------------------------------
def test_retry_recupera_depois_de_503():
    srv = HTTPLocal(porta=8799, chuva_mm=12.5, falhas_iniciais=2).iniciar()
    try:
        clima = integracoes.ClimaOpenMeteo("http://127.0.0.1:8799/x", timeout=2, tentativas=3, espera_base=0)
        assert clima.chuva_hoje_mm(-23.5, -46.6) == 12.5
        assert srv.chamadas == 3
    finally:
        srv.parar()


def test_api_fora_do_ar_devolve_none_sem_quebrar():
    clima = integracoes.ClimaOpenMeteo("http://127.0.0.1:9/x", timeout=1, tentativas=2, espera_base=0)
    assert clima.chuva_hoje_mm(-23.5, -46.6) is None


# --- banco + ponta a ponta ----------------------------------------------------------
def test_banco_e_idempotente(tmp_path):
    b = Banco(tmp_path / "t.db")
    b.iniciar_execucao("r1")
    dados = dict(chave="k1", canal="sp156", id_origem="1", recebido_em="2026-11-18T10:00", bairro="Lapa",
                 descricao="x" * 20, dados_removidos="", categoria="lixo_entulho", confianca=0.9,
                 origem_classificacao="NLP local", urgencia="media", justificativa="", orgao="SP Regula",
                 prazo_dias=10, chuva_mm=None, status="encaminhado", motivos_revisao="", run_id="r1")
    assert b.inserir_solicitacao(dados, None) == "ZR-2026-000001"
    assert b.inserir_solicitacao(dados, None) is None


def test_ponta_a_ponta_e_reexecucao(cfg):
    gerar_lote_demo(cfg.pasta_entrada)
    r1 = executar(cfg)
    assert r1["status"] != "falhou" and r1["contagens"]["novos"] == 16
    assert list((cfg.pasta_saida / r1["run_id"] / "despachos").glob("*.xlsx"))
    gerar_lote_demo(cfg.pasta_entrada)
    r2 = executar(cfg)
    assert r2["contagens"]["novos"] == 0 and r2["contagens"]["ja_processados"] == 16
