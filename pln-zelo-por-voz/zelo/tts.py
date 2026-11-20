"""Módulo TTS (Text-to-Speech) em português do Brasil.

- EdgeTTS (padrão): vozes neurais pt-BR da Microsoft (pt-BR-FranciscaNeural),
  gratuitas, sem chave de API. Precisa de internet. Voz sintética pronta,
  sem clonagem de voz de pessoa real.
- MacSayTTS (alternativa offline): comando `say` do macOS com a voz Luciana.
"""
from __future__ import annotations

import asyncio
import shutil
import subprocess
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

from .config import settings


@dataclass
class TTSResult:
    audio_path: str
    elapsed_s: float
    engine: str


def _out_path(ext: str) -> Path:
    return settings.tmp_audio_dir / f"resposta_{uuid.uuid4().hex[:10]}.{ext}"


class EdgeTTS:
    def __init__(self, voice: str | None = None, rate: str | None = None):
        self.voice = voice or settings.tts_voice
        self.rate = rate or settings.tts_rate

    @property
    def name(self) -> str:
        return f"edge-tts:{self.voice}"

    async def _save(self, text: str, path: Path) -> None:
        import edge_tts

        await edge_tts.Communicate(text, self.voice, rate=self.rate).save(str(path))

    def synthesize(self, text: str, out_path: str | Path | None = None) -> TTSResult:
        path = Path(out_path) if out_path else _out_path("mp3")
        t0 = time.perf_counter()
        try:
            asyncio.run(self._save(text, path))
        except RuntimeError:
            # Já existe um event loop rodando nesta thread: usa um loop novo.
            loop = asyncio.new_event_loop()
            try:
                loop.run_until_complete(self._save(text, path))
            finally:
                loop.close()
        return TTSResult(str(path), time.perf_counter() - t0, self.name)


class MacSayTTS:
    def __init__(self, voice: str | None = None):
        self.voice = voice or settings.tts_mac_voice
        if not shutil.which("say"):
            raise RuntimeError("O comando 'say' só existe no macOS.")

    @property
    def name(self) -> str:
        return f"macos-say:{self.voice}"

    def synthesize(self, text: str, out_path: str | Path | None = None) -> TTSResult:
        path = Path(out_path) if out_path else _out_path("wav")
        aiff = path.with_suffix(".aiff")
        t0 = time.perf_counter()
        subprocess.run(["say", "-v", self.voice, "-o", str(aiff), text], check=True)
        subprocess.run(["afconvert", "-f", "WAVE", "-d", "LEI16", str(aiff), str(path)], check=True)
        aiff.unlink(missing_ok=True)
        return TTSResult(str(path), time.perf_counter() - t0, self.name)


class FallbackTTS:
    """Tenta o motor principal e, se falhar (ex.: sem internet), usa o reserva."""

    def __init__(self, primary, backup=None):
        self.primary = primary
        self.backup = backup

    @property
    def name(self) -> str:
        return self.primary.name

    def synthesize(self, text: str, out_path: str | Path | None = None) -> TTSResult:
        try:
            return self.primary.synthesize(text, out_path)
        except Exception:
            if self.backup is None:
                raise
            return self.backup.synthesize(text, None)


def build_tts(provider: str | None = None):
    provider = (provider or settings.tts_provider).lower()
    if provider == "mac":
        return MacSayTTS()
    backup = None
    if shutil.which("say"):
        try:
            backup = MacSayTTS()
        except RuntimeError:
            backup = None
    return FallbackTTS(EdgeTTS(), backup)
