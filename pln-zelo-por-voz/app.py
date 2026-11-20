"""Interface Gradio do Zelo: fale, ouça a resposta e veja tudo em texto.

Rode com:  python app.py
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TMP = ROOT / ".tmp_audio"
# Gradio guarda as gravações aqui; limpamos ao iniciar e apagamos cada áudio após a transcrição.
shutil.rmtree(TMP, ignore_errors=True)
TMP.mkdir(exist_ok=True)
os.environ["GRADIO_TEMP_DIR"] = str(TMP)

import gradio as gr  # noqa: E402

from zelo.config import settings  # noqa: E402
from zelo.llm import build_llm  # noqa: E402
from zelo.pipeline import Conversation, VoicePipeline  # noqa: E402
from zelo.privacy import CONSENT_TEXT  # noqa: E402
from zelo.stt import WhisperSTT  # noqa: E402
from zelo.tts import build_tts  # noqa: E402

print(f"Carregando Whisper '{settings.stt_model}' (a primeira vez baixa o modelo)...")
stt = WhisperSTT()
stt.warmup()
pipeline = VoicePipeline(stt=stt, llm=build_llm(), tts=build_tts())
print(f"STT: {stt.name} | LLM: {pipeline.llm.name} | TTS: {pipeline.tts.name}")

CSS = """
.gradio-container {font-size: 18px !important; max-width: 1100px !important; margin: auto;}
#titulo h1 {font-size: 2.2rem;}
#latencia {font-family: ui-monospace, monospace; font-size: 15px;}
button.lg {font-size: 1.15rem !important; min-height: 56px;}
"""

WELCOME = "Olá! Eu sou o Zelo. Posso explicar como pedir tapa-buraco, poda de árvore, conserto de iluminação, descarte de entulho e outros serviços da cidade. Como posso ajudar?"


def _sources_md(result) -> str:
    if not result.sources:
        return "_Nenhum trecho da base foi usado nesta resposta._"
    lines = []
    for c in result.sources:
        url = c.source.split(";")[0].strip()
        lines.append(f"- **{c.doc}**, seção _{c.title}_ ({url})")
    return "\n".join(lines)


def _respond(result, chat, conv):
    if not result.transcript:
        chat = chat + [{"role": "assistant", "content": "Não consegui ouvir nada no áudio. Pode tentar de novo, mais perto do microfone?"}]
        return chat, None, "", "Sem fala detectada.", "", conv
    chat = chat + [
        {"role": "user", "content": result.transcript},
        {"role": "assistant", "content": result.answer},
    ]
    status = result.timer.summary()
    if result.audio_deleted:
        status += "\nÁudio do usuário apagado após a transcrição."
    if result.masked_transcript != result.transcript:
        status += "\nDados pessoais mascarados antes do envio ao LLM."
    if result.emergency:
        status += "\nPossível emergência detectada: resposta priorizou números de emergência."
    return chat, result.audio_path, result.spoken_text, status, _sources_md(result), conv


import threading  # noqa: E402

_PROCESSED: set[str] = set()
_LOCK = threading.Lock()


def on_audio(audio_path, chat, conv):
    if not audio_path:
        return chat, None, "", "Grave ou envie um áudio.", "", conv
    # O Gradio dispara mais de um evento para a mesma gravação (parar de gravar
    # e arquivo recebido). Só o primeiro processa; os outros são ignorados, sem
    # mexer na tela, porque o áudio já foi transcrito e apagado.
    with _LOCK:
        if audio_path in _PROCESSED or not os.path.exists(audio_path):
            return tuple(gr.skip() for _ in range(6))
        _PROCESSED.add(audio_path)
    try:
        result = pipeline.run_audio(audio_path, conv)
    except Exception as exc:  # mostra o erro na tela sem derrubar o app
        return chat, None, "", f"Erro: {exc}", "", conv
    return _respond(result, chat, conv)


def on_text(text, chat, conv):
    if not text or not text.strip():
        return chat, None, "", "", "", conv, ""
    from zelo.latency import TurnTimer

    try:
        result = pipeline.run_text(text.strip(), conv, timer=TurnTimer())
    except Exception as exc:
        return chat, None, "", f"Erro: {exc}", "", conv, text
    return (*_respond(result, chat, conv), "")


def new_conversation():
    return [{"role": "assistant", "content": WELCOME}], None, "", "", "", Conversation(), None


def accept(consent):
    if not consent:
        gr.Warning("Para usar o Zelo, marque a caixa de consentimento.")
        return gr.update(visible=True), gr.update(visible=False)
    return gr.update(visible=False), gr.update(visible=True)


with gr.Blocks(title="Zelo | Assistente de voz da zeladoria urbana", delete_cache=(600, 1800)) as demo:
    conv_state = gr.State(Conversation())

    gr.Markdown("# Zelo\nAssistente de voz para serviços de zeladoria da cidade de São Paulo", elem_id="titulo")

    with gr.Column(visible=True) as consent_box:
        gr.Markdown(CONSENT_TEXT)
        consent_chk = gr.Checkbox(label="Li e concordo que minha fala seja gravada e processada como descrito acima.")
        consent_btn = gr.Button("Começar a conversa", variant="primary", size="lg")

    with gr.Column(visible=False) as main_box:
        with gr.Row():
            with gr.Column(scale=5):
                chatbot = gr.Chatbot(
                    value=[{"role": "assistant", "content": WELCOME}],
                    label="Conversa (transcrição e resposta em texto)",
                    height=430,
                )
                answer_audio = gr.Audio(label="Resposta falada", autoplay=True, interactive=False, type="filepath")
            with gr.Column(scale=4):
                mic = gr.Audio(
                    sources=["microphone", "upload"],
                    type="filepath",
                    label="Aperte para falar (ou envie um arquivo de áudio)",
                )
                send_btn = gr.Button("Enviar áudio", variant="primary", size="lg")
                with gr.Accordion("Prefere digitar?", open=False):
                    txt = gr.Textbox(label="Pergunta por texto", placeholder="Ex.: como peço tapa-buraco?")
                    txt_btn = gr.Button("Enviar texto")
                latency = gr.Textbox(label="Latência por etapa e privacidade", lines=4, elem_id="latencia", interactive=False)
                spoken = gr.Textbox(label="Texto adaptado para a fala (enviado ao TTS)", lines=3, interactive=False)
                with gr.Accordion("Fontes usadas na resposta", open=False):
                    sources = gr.Markdown()
                clear_btn = gr.Button("Nova conversa")

    outs = [chatbot, answer_audio, spoken, latency, sources, conv_state]
    consent_btn.click(accept, consent_chk, [consent_box, main_box])
    mic.stop_recording(on_audio, [mic, chatbot, conv_state], outs).then(lambda: None, None, mic)
    mic.upload(on_audio, [mic, chatbot, conv_state], outs).then(lambda: None, None, mic)
    send_btn.click(on_audio, [mic, chatbot, conv_state], outs).then(lambda: None, None, mic)
    txt.submit(on_text, [txt, chatbot, conv_state], [*outs, txt])
    txt_btn.click(on_text, [txt, chatbot, conv_state], [*outs, txt])
    clear_btn.click(new_conversation, None, [*outs, mic])


if __name__ == "__main__":
    demo.queue().launch(
        theme=gr.themes.Soft(primary_hue="green", text_size="lg"),
        css=CSS,
        allowed_paths=[str(TMP)],
        inbrowser=True,
    )
