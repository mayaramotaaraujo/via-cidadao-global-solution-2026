"""Funções compartilhadas pelos scripts de avaliação."""
from __future__ import annotations

import re
import statistics as st
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from zelo.speech_adapter import normalize_numbers  # noqa: E402

RESULTS = ROOT / "results"
RESULTS.mkdir(exist_ok=True)
MATERIAL = ROOT / "material_teste"
AUDIO_EXTS = [".wav", ".m4a", ".mp3", ".ogg", ".webm", ".flac", ".aac", ".mp4"]


def normalize_for_wer(text: str) -> str:
    """Normalização aplicada igualmente à referência e à hipótese antes do WER.

    Minúsculas, números por extenso, hífen vira espaço, sem pontuação.
    Assim "156" e "cento e cinquenta e seis" contam como iguais, mas erros
    reais de palavra continuam sendo contados.
    """
    text = unicodedata.normalize("NFC", text or "")
    text = normalize_numbers(text)
    text = text.lower().replace("-", " ")
    text = re.sub(r"[^\w\sà-ú]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def find_audio(folder: Path, name: str) -> Path | None:
    """Acha o arquivo mesmo que a extensão gravada seja outra (.m4a, .mp3...)."""
    p = folder / name
    if p.exists():
        return p
    for ext in AUDIO_EXTS:
        cand = folder / (Path(name).stem + ext)
        if cand.exists():
            return cand
    return None


def describe(values: list[float]) -> dict:
    if not values:
        return {"n": 0, "media": 0, "mediana": 0, "p90": 0, "min": 0, "max": 0}
    vs = sorted(values)
    p90 = vs[min(len(vs) - 1, int(round(0.9 * (len(vs) - 1))))]
    return {
        "n": len(vs),
        "media": round(st.mean(vs), 3),
        "mediana": round(st.median(vs), 3),
        "p90": round(p90, 3),
        "min": round(vs[0], 3),
        "max": round(vs[-1], 3),
    }
