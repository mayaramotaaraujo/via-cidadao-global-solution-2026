"""Testes unitários (não precisam de internet nem de chave de API).

Rode com:  python -m pytest -q
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from eval.common import normalize_for_wer  # noqa: E402
from zelo.knowledge import KnowledgeBase  # noqa: E402
from zelo.latency import TurnTimer  # noqa: E402
from zelo.llm import LLMResult  # noqa: E402
from zelo.pipeline import Conversation, VoicePipeline  # noqa: E402
from zelo.privacy import detect_emergency, mask_pii, secure_delete  # noqa: E402
from zelo.speech_adapter import adapt_for_speech  # noqa: E402

# ---------------- Adaptação para fala ----------------


def test_remove_markdown_e_emoji():
    out = adapt_for_speech("**Ligue no 156** 😊\n- item")
    assert "*" not in out and "😊" not in out and "-" not in out
    assert "cento e cinquenta e seis" in out


def test_telefones_lidos_digito_a_digito():
    assert "zero oitocentos, sete sete nove, zero um cinco seis" in adapt_for_speech("Ligue 0800 779 0156.")
    assert "quatro zero um nove nove" in adapt_for_speech("Envie para 40199.")


def test_siglas_datas_horas_dinheiro():
    out = adapt_for_speech("Envie SMS pelo SP156 em 19/11/2026 às 8h30. Multa de R$ 17.447,82.")
    assert "esse eme esse" in out and "esse pê cento e cinquenta e seis" in out
    assert "dezenove de novembro de dois mil e vinte e seis" in out
    assert "oito horas e trinta" in out
    assert "dezessete mil, quatrocentos e quarenta e sete reais e oitenta e dois centavos" in out


def test_unidades_e_links():
    out = adapt_for_speech("Leve até 1 m³ em https://prefeitura.sp.gov.br/sp-mais-limpo")
    assert "um metro cúbico" in out and "http" not in out


def test_sem_digitos_no_texto_falado():
    out = adapt_for_speech("Defesa Civil 199, Bombeiros 193, 5 dias, 90 dias, 52%.")
    assert not any(ch.isdigit() for ch in out)


# ---------------- Privacidade ----------------


def test_mask_pii():
    out = mask_pii("Meu CPF é 123.456.789-09, telefone (11) 98765-4321, email a@b.com, CEP 01310-100")
    assert "123.456" not in out and "98765" not in out and "a@b.com" not in out and "01310" not in out
    assert "[CPF]" in out and "[TELEFONE]" in out and "[EMAIL]" in out and "[CEP]" in out


def test_mask_nao_estraga_numeros_de_servico():
    assert mask_pii("ligue 156 ou 199") == "ligue 156 ou 199"


def test_secure_delete(tmp_path):
    f = tmp_path / "a.wav"
    f.write_bytes(b"abc")
    assert secure_delete(f) and not f.exists()


def test_detect_emergency():
    assert detect_emergency("o fio está soltando faísca")
    assert detect_emergency("Tem um incêndio aqui")
    assert not detect_emergency("como peço tapa-buraco?")


# ---------------- RAG ----------------


def test_rag_encontra_tema_certo():
    kb = KnowledgeBase()
    assert kb.search("como peço tapa buraco").chunks[0].doc == "Tapa-buraco"
    assert "Ecoponto" in kb.search("quanto entulho posso levar").chunks[0].doc
    assert "Iluminação" in kb.search("poste apagado de noite").chunks[0].doc
    assert "Veículo" in kb.search("carro abandonado na rua").chunks[0].doc


def test_rag_tolera_erro_de_transcricao():
    kb = KnowledgeBase()
    assert "Bueiros" in kb.search("o boeiro ta entupido").chunks[0].doc


# ---------------- Pipeline com componentes falsos ----------------


class FakeLLM:
    name = "fake"

    def __init__(self):
        self.last_messages = None

    def chat(self, messages):
        self.last_messages = messages
        return LLMResult("**Ligue no 156**, é de graça! 😊", 0.01, "fake")


class FakeSTT:
    name = "fake-stt"

    def transcribe(self, path):
        from zelo.stt import STTResult

        return STTResult("meu cpf é 123.456.789-09, como peço poda?", "pt", 2.0, 0.01)


def test_pipeline_memoria_mascaramento_e_apaga_audio(tmp_path):
    llm = FakeLLM()
    pipe = VoicePipeline(stt=FakeSTT(), llm=llm, tts=None, log_latency=False)
    conv = Conversation()
    audio = tmp_path / "fala.wav"
    audio.write_bytes(b"RIFF....")
    res = pipe.run_audio(str(audio), conv)

    assert res.audio_deleted and not audio.exists()           # retenção mínima
    assert "123.456" not in llm.last_messages[-1]["content"]  # LGPD: CPF não vai ao LLM
    assert "*" not in res.spoken_text and "😊" not in res.spoken_text
    assert len(conv.messages) == 2                             # memória guardada

    pipe.run_text("e onde eu faço isso?", conv, TurnTimer(), synthesize=False)
    roles = [m["role"] for m in llm.last_messages]
    assert roles == ["system", "user", "assistant", "user"]   # histórico enviado
    assert "Árvore" in llm.last_messages[0]["content"] or "árvore" in llm.last_messages[0]["content"]


def test_normalizacao_wer():
    assert normalize_for_wer("Ligue no 156!") == normalize_for_wer("ligue no cento e cinquenta e seis")
    assert normalize_for_wer("Cata-Bagulho") == "cata bagulho"
