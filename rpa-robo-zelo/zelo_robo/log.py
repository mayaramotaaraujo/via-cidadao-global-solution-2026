"""Configuração de log: console (resumido) + arquivo logs/robo.log (detalhado)."""

from __future__ import annotations

import logging
from pathlib import Path

from .privacidade import FiltroPII

FORMATO = "%(asctime)s | %(levelname)-7s | %(name)-18s | %(message)s"


def configurar_log(pasta_logs: Path, run_id: str, nivel_console: int = logging.INFO) -> Path:
    pasta_logs.mkdir(parents=True, exist_ok=True)
    caminho = pasta_logs / "robo.log"

    raiz = logging.getLogger("zelo")
    raiz.setLevel(logging.DEBUG)
    for h in list(raiz.handlers):
        raiz.removeHandler(h)
        h.close()

    filtro = FiltroPII()
    arquivo = logging.FileHandler(caminho, encoding="utf-8")
    arquivo.setLevel(logging.DEBUG)
    arquivo.setFormatter(logging.Formatter(FORMATO.replace("| %(message)s", f"| {run_id} | %(message)s")))
    arquivo.addFilter(filtro)

    console = logging.StreamHandler()
    console.setLevel(nivel_console)
    console.setFormatter(logging.Formatter("%(levelname)-7s %(message)s"))
    console.addFilter(filtro)

    raiz.addHandler(arquivo)
    raiz.addHandler(console)
    raiz.propagate = False
    return caminho
