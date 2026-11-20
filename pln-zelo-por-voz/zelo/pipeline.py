"""Orquestra um turno: áudio -> STT -> (privacidade) -> RAG -> LLM -> adaptação -> TTS.

Cada etapa é um objeto independente injetado no construtor, então qualquer
componente pode ser trocado (outro Whisper, outro LLM, outro TTS) sem mexer
no resto do fluxo.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .config import settings
from .knowledge import Chunk, KnowledgeBase
from .latency import LatencyLogger, TurnTimer
from .privacy import detect_emergency, ensure_emergency_number, mask_pii, secure_delete
from .prompts import CONTEXT_TEMPLATE, EMERGENCY_NOTE, NO_CONTEXT, SYSTEM_PROMPT
from .speech_adapter import adapt_for_speech


@dataclass
class TurnResult:
    transcript: str
    masked_transcript: str
    answer: str
    spoken_text: str
    audio_path: str | None
    timer: TurnTimer
    sources: list[Chunk] = field(default_factory=list)
    emergency: bool = False
    audio_deleted: bool = False
    model_version: str = ""


class Conversation:
    """Memória da conversa (somente em RAM, nunca em disco)."""

    def __init__(self, max_turns: int | None = None):
        self.max_turns = max_turns or settings.history_turns
        self.messages: list[dict] = []

    def add(self, user: str, assistant: str) -> None:
        self.messages += [{"role": "user", "content": user}, {"role": "assistant", "content": assistant}]
        self.messages = self.messages[-2 * self.max_turns :]

    def last_user(self) -> str | None:
        for m in reversed(self.messages):
            if m["role"] == "user":
                return m["content"]
        return None

    def clear(self) -> None:
        self.messages = []


class VoicePipeline:
    def __init__(self, stt=None, llm=None, tts=None, kb: KnowledgeBase | None = None, log_latency: bool = True):
        self.stt = stt
        self.llm = llm
        self.tts = tts
        self.kb = kb or KnowledgeBase()
        self.logger = LatencyLogger() if log_latency else None

    # ---------- RAG com suporte a perguntas de continuação ----------
    def retrieve(self, question: str, conv: Conversation) -> list[Chunk]:
        res = self.kb.search(question)
        scored = {id(c): (c, s) for c, s in zip(res.chunks, res.scores)}
        prev = conv.last_user()
        if prev:
            # Pergunta de continuação ("e onde eu faço isso?") herda o assunto anterior.
            res2 = self.kb.search(f"{prev} {question}")
            for c, s in zip(res2.chunks, res2.scores):
                if id(c) not in scored or scored[id(c)][1] < s:
                    scored[id(c)] = (c, s)
        ranked = sorted(scored.values(), key=lambda x: x[1], reverse=True)[: settings.rag_top_k]
        return [c for c, _ in ranked]

    def build_messages(self, question: str, chunks: list[Chunk], conv: Conversation, emergency: bool) -> list[dict]:
        context = CONTEXT_TEMPLATE.format(context="\n\n".join(c.as_context() for c in chunks)) if chunks else NO_CONTEXT
        system = SYSTEM_PROMPT + "\n" + context + ("\n" + EMERGENCY_NOTE if emergency else "")
        return [{"role": "system", "content": system}, *conv.messages, {"role": "user", "content": question}]

    # ---------- Turno a partir de texto ----------
    def run_text(self, text: str, conv: Conversation, timer: TurnTimer | None = None, synthesize: bool = True) -> TurnResult:
        timer = timer or TurnTimer()
        masked = mask_pii(text)
        emergency = detect_emergency(text)

        with timer.stage("rag"):
            chunks = self.retrieve(masked, conv)
        with timer.stage("llm"):
            llm_res = self.llm.chat(self.build_messages(masked, chunks, conv, emergency))
            answer = ensure_emergency_number(text, llm_res.text)
        with timer.stage("adapt"):
            spoken = adapt_for_speech(answer)

        audio_path = None
        if synthesize and self.tts is not None:
            with timer.stage("tts"):
                audio_path = self.tts.synthesize(spoken).audio_path

        conv.add(masked, answer)
        return TurnResult(text, masked, answer, spoken, audio_path, timer, chunks, emergency,
                          model_version=getattr(llm_res, "model_version", ""))

    # ---------- Turno completo a partir de áudio ----------
    def run_audio(self, audio_path: str, conv: Conversation, delete_audio: bool = True, source: str = "app") -> TurnResult:
        timer = TurnTimer()
        try:
            with timer.stage("stt"):
                transcript = self.stt.transcribe(audio_path).text
        finally:
            deleted = secure_delete(audio_path) if delete_audio else False

        if not transcript:
            transcript = ""
            result = TurnResult("", "", "", "", None, timer, audio_deleted=deleted)
            return result

        result = self.run_text(transcript, conv, timer=timer)
        result.audio_deleted = deleted
        if self.logger:
            self.logger.log(timer, {
                "stt_model": getattr(self.stt, "name", ""),
                "llm_model": getattr(self.llm, "name", ""),
                "tts_engine": getattr(self.tts, "name", ""),
                "source": source,
            })
        return result
