"""Monta uma sequência de quadros a partir de recortes do conjunto de TESTE.

Serve para demonstrar o processamento de vídeo quando não há um vídeo real de
superfície. Cada quadro é um mosaico de 4 por 2 recortes de 256x256 (1024x512).
Como eu sei de qual recorte veio cada pedaço, sei também a resposta certa de cada
quadro e posso medir se o sistema acertou. É uma simulação: o mosaico não é uma
cena real, então o resultado mostra o funcionamento do fluxo e não o desempenho em rua.
"""
import json
from pathlib import Path

import cv2
import numpy as np


def montar_sequencia(df_teste, pasta, quadros=30, inicio_evento=10, fim_evento=19, semente=0):
    """Quadros dentro do intervalo do evento têm 1 recorte com fissura; os outros só têm recortes sem fissura."""
    rng = np.random.default_rng(semente)
    pasta = Path(pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    pos = df_teste[df_teste["rotulo"] == 1]["caminho"].tolist()
    neg = df_teste[df_teste["rotulo"] == 0]["caminho"].tolist()
    if not pos or not neg:
        raise ValueError("O conjunto de teste precisa ter recortes com e sem fissura.")
    verdade = []
    for i in range(quadros):
        evento = inicio_evento <= i <= fim_evento
        caminhos = list(rng.choice(neg, 8, replace=True))
        if evento:
            caminhos[5] = str(rng.choice(pos))
        blocos = [cv2.resize(cv2.imread(c), (256, 256)) for c in caminhos]
        quadro = np.concatenate([np.concatenate(blocos[:4], axis=1), np.concatenate(blocos[4:], axis=1)], axis=0)
        cv2.imwrite(str(pasta / f"quadro_{i:03d}.jpg"), quadro)
        verdade.append(bool(evento))
    (pasta / "verdade.json").write_text(json.dumps(verdade), encoding="utf-8")
    return verdade


def comparar_com_verdade(resumo, verdade, cada_n=1):
    """Compara os quadros marcados como positivos com a verdade do mosaico."""
    tp = fp = fn = tn = 0
    for q in resumo["quadros"]:
        real = verdade[q["quadro"]]
        if q["positivo"] and real:
            tp += 1
        elif q["positivo"] and not real:
            fp += 1
        elif not q["positivo"] and real:
            fn += 1
        else:
            tn += 1
    return {"tp": tp, "fp": fp, "fn": fn, "tn": tn,
            "precisao": round(tp / (tp + fp), 4) if (tp + fp) else None,
            "revocacao": round(tp / (tp + fn), 4) if (tp + fn) else None}
