"""Registro de latência por etapa. Grava só tempos, nunca o conteúdo da conversa."""
from __future__ import annotations

import csv
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from .config import settings

STAGES = ["stt", "rag", "llm", "adapt", "tts"]


@dataclass
class TurnTimer:
    times: dict[str, float] = field(default_factory=dict)

    @contextmanager
    def stage(self, name: str):
        t0 = time.perf_counter()
        try:
            yield
        finally:
            self.times[name] = time.perf_counter() - t0

    @property
    def total(self) -> float:
        """Tempo do fim da fala até o áudio da resposta estar pronto para tocar."""
        return sum(self.times.get(s, 0.0) for s in STAGES)

    def summary(self) -> str:
        parts = [f"{s.upper()} {self.times.get(s, 0):.2f}s" for s in STAGES if s in self.times]
        return " | ".join(parts) + f" | TOTAL até a fala {self.total:.2f}s"


class LatencyLogger:
    def __init__(self, path: Path | None = None):
        self.path = path or settings.logs_dir / "latency.csv"

    def log(self, timer: TurnTimer, meta: dict) -> None:
        new = not self.path.exists()
        with open(self.path, "a", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            if new:
                w.writerow(["timestamp", *[f"{s}_s" for s in STAGES], "total_s", "stt_model", "llm_model", "tts_engine", "source"])
            w.writerow([
                datetime.now().isoformat(timespec="seconds"),
                *[f"{timer.times.get(s, 0):.3f}" for s in STAGES],
                f"{timer.total:.3f}",
                meta.get("stt_model", ""), meta.get("llm_model", ""), meta.get("tts_engine", ""), meta.get("source", "app"),
            ])
