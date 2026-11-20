"""Configuração central do Zelo. Tudo vem de variáveis de ambiente (.env),
para que cada componente possa ser trocado sem mexer no código."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")


def _env(name: str, default: str) -> str:
    return os.getenv(name, default).strip()


@dataclass
class Settings:
    # STT
    stt_model: str = field(default_factory=lambda: _env("ZELO_STT_MODEL", "small"))
    stt_device: str = field(default_factory=lambda: _env("ZELO_STT_DEVICE", "cpu"))
    stt_compute_type: str = field(default_factory=lambda: _env("ZELO_STT_COMPUTE", "int8"))
    stt_beam_size: int = field(default_factory=lambda: int(_env("ZELO_STT_BEAM", "1")))

    # LLM
    llm_provider: str = field(default_factory=lambda: _env("ZELO_LLM_PROVIDER", "openai"))
    llm_model: str = field(default_factory=lambda: _env("ZELO_LLM_MODEL", "gpt-4o-mini"))
    llm_temperature: float = field(default_factory=lambda: float(_env("ZELO_LLM_TEMPERATURE", "0.2")))
    llm_max_tokens: int = field(default_factory=lambda: int(_env("ZELO_LLM_MAX_TOKENS", "220")))
    ollama_url: str = field(default_factory=lambda: _env("OLLAMA_URL", "http://localhost:11434"))

    # Memória e RAG
    history_turns: int = field(default_factory=lambda: int(_env("ZELO_HISTORY_TURNS", "6")))
    rag_top_k: int = field(default_factory=lambda: int(_env("ZELO_RAG_TOP_K", "4")))
    rag_min_score: float = field(default_factory=lambda: float(_env("ZELO_RAG_MIN_SCORE", "0.08")))

    # TTS
    tts_provider: str = field(default_factory=lambda: _env("ZELO_TTS_PROVIDER", "edge"))
    tts_voice: str = field(default_factory=lambda: _env("ZELO_TTS_VOICE", "pt-BR-FranciscaNeural"))
    tts_rate: str = field(default_factory=lambda: _env("ZELO_TTS_RATE", "-5%"))
    tts_mac_voice: str = field(default_factory=lambda: _env("ZELO_TTS_MAC_VOICE", "Luciana"))

    # Pastas
    kb_dir: Path = ROOT / "kb"
    logs_dir: Path = ROOT / "logs"
    tmp_audio_dir: Path = ROOT / ".tmp_audio"


settings = Settings()
settings.logs_dir.mkdir(exist_ok=True)
settings.tmp_audio_dir.mkdir(exist_ok=True)
