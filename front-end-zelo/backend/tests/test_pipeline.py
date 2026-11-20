from app.pipelines.anonimizacao import anonimizar
from app.pipelines.regras import aplicar_regras, orgao_para
from app.schemas.relato import Categoria, ContextoClima, Urgencia
from tests.conftest import analise_llm


def test_anonimiza_varios_formatos():
    texto, tipos = anonimizar("Fone 11 91234-5678, email a.b@c.com.br, placa ABC1D23, cpf 12345678900")
    assert "91234-5678" not in texto
    assert "a.b@c.com.br" not in texto
    assert "ABC1D23" not in texto
    assert "12345678900" not in texto
    assert set(tipos) == {"telefone", "e-mail", "placa de veículo", "CPF"}


def test_texto_sem_dados_pessoais_fica_intacto():
    texto = "Buraco na Rua da Mooca, altura do número 1200"
    assert anonimizar(texto) == (texto, [])


def test_risco_imediato_eleva_urgencia():
    analise, ajustes, _ = aplicar_regras(analise_llm(urgencia=Urgencia.BAIXA, risco_imediato=True), "texto", None)
    assert analise.urgencia == Urgencia.ALTA
    assert ajustes


def test_chuva_forte_eleva_alagamento():
    clima = ContextoClima(chuva_prevista_mm=35)
    analise, ajustes, _ = aplicar_regras(analise_llm(categoria=Categoria.ALAGAMENTO, urgencia=Urgencia.MEDIA), "bueiro", clima)
    assert analise.urgencia == Urgencia.ALTA
    assert "35 mm" in ajustes[0]


def test_chuva_nao_afeta_buraco():
    clima = ContextoClima(chuva_prevista_mm=35)
    analise, ajustes, _ = aplicar_regras(analise_llm(categoria=Categoria.BURACO), "buraco", clima)
    assert analise.urgencia == Urgencia.MEDIA and not ajustes


def test_baixa_confianca_pede_revisao_humana():
    _, _, motivos = aplicar_regras(analise_llm(confianca=0.4), "texto", None)
    assert any("certeza" in m for m in motivos)


def test_termo_de_risco_com_urgencia_baixa_pede_revisao():
    _, _, motivos = aplicar_regras(analise_llm(urgencia=Urgencia.BAIXA), "tem um fio solto no chão", None)
    assert any("risco" in m for m in motivos)


def test_confianca_fora_do_intervalo_e_normalizada():
    analise, _, _ = aplicar_regras(analise_llm(confianca=1.7), "texto", None)
    assert analise.confianca == 1.0


def test_orgao_com_defesa_civil_em_risco():
    assert "Defesa Civil" in orgao_para(Categoria.ARVORE, True)
    assert "Defesa Civil" not in orgao_para(Categoria.ARVORE, False)
