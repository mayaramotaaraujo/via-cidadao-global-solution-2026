"""Módulo STT (Speech-to-Text).

Usa faster-whisper rodando LOCALMENTE: o áudio do cidadão nunca sai da máquina.
Para trocar o motor de STT, basta criar outra classe com o método
`transcribe(path) -> STTResult`.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from functools import lru_cache

from .config import settings


def _patch_pyav() -> None:
    """Compatibilidade: o PyAV 15+ removeu o argumento `metadata_errors`,
    que o faster-whisper 1.2.1 ainda passa para av.open()."""
    try:
        import av
    except ImportError:
        return
    if getattr(av.open, "_zelo_patched", False):
        return
    original = av.open

    def _open(*args, **kwargs):
        try:
            return original(*args, **kwargs)
        except TypeError as exc:
            if "metadata_errors" not in str(exc):
                raise
            kwargs.pop("metadata_errors", None)
            return original(*args, **kwargs)

    _open._zelo_patched = True
    av.open = _open


_patch_pyav()

# Vocabulário do domínio: ajuda o Whisper a acertar termos de zeladoria.
DOMAIN_PROMPT = (
    "Conversa sobre zeladoria urbana em São Paulo: SP156, tapa-buraco, "
    "boca de lobo, bueiro, Ecoponto, Cata-Bagulho, poda de árvore, "
    "iluminação pública, entulho, Defesa Civil, Subprefeitura, Sabesp, "
    "Enel, Comgás, Mooca, alagamento, caçamba."
)


@dataclass
class STTResult:
    text: str
    language: str
    duration_audio_s: float
    elapsed_s: float


@lru_cache(maxsize=4)
def _load_model(size: str, device: str, compute_type: str):
    from faster_whisper import WhisperModel

    return WhisperModel(size, device=device, compute_type=compute_type)


class WhisperSTT:
    def __init__(
        self,
        model_size: str | None = None,
        device: str | None = None,
        compute_type: str | None = None,
        beam_size: int | None = None,
        use_domain_prompt: bool = True,
    ) -> None:
        self.model_size = model_size or settings.stt_model
        self.device = device or settings.stt_device
        self.compute_type = compute_type or settings.stt_compute_type
        self.beam_size = beam_size or settings.stt_beam_size
        self.use_domain_prompt = use_domain_prompt

    @property
    def name(self) -> str:
        return f"faster-whisper-{self.model_size}"

    def warmup(self) -> None:
        _load_model(self.model_size, self.device, self.compute_type)

    def transcribe(self, audio_path: str) -> STTResult:
        model = _load_model(self.model_size, self.device, self.compute_type)
        t0 = time.perf_counter()
        segments, info = model.transcribe(
            audio_path,
            language="pt",
            beam_size=self.beam_size,
            vad_filter=True,
            initial_prompt=DOMAIN_PROMPT if self.use_domain_prompt else None,
        )
        text = " ".join(s.text.strip() for s in segments).strip()
        elapsed = time.perf_counter() - t0
        return STTResult(
            text=text,
            language=info.language,
            duration_audio_s=float(info.duration),
            elapsed_s=elapsed,
        )
