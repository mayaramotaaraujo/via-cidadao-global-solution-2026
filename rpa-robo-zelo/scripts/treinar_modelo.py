"""Treina o classificador e salva em modelos/classificador.joblib.

Uso: python -m scripts.treinar_modelo
"""

from __future__ import annotations

import logging

from sklearn.model_selection import cross_val_score
import pandas as pd

from zelo_robo.classificador import criar_pipeline, treinar
from zelo_robo.config import Config

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    cfg = Config.carregar()
    df = pd.read_csv(cfg.caminho_treino)
    notas = cross_val_score(criar_pipeline(), df["descricao"], df["categoria"], cv=5, scoring="f1_macro")
    print(f"Validação cruzada (5 partes) na base de treino: F1 macro = {notas.mean():.3f} ± {notas.std():.3f}")
    print("Obs.: a base de treino é sintética e repetitiva; a métrica que vale é a do conjunto de teste "
          "escrito à mão (python -m scripts.validar).")
    treinar(cfg.caminho_treino, cfg.caminho_modelo)
    print(f"Modelo salvo em {cfg.caminho_modelo}")
