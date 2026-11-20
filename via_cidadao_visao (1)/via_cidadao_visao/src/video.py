"""Imagem única, sequência de imagens e vídeo curto com o modelo treinado.

O modelo foi treinado com recortes de 256x256. Uma foto ou um quadro de vídeo é
maior que isso, então eu corto o quadro numa grade de recortes de 256x256, classifico
cada recorte e marco os que passam do limiar. A confiança do quadro é a maior
probabilidade entre os recortes.
"""
import json
import time
from pathlib import Path

import cv2
import numpy as np
import torch

from modelo import MEDIA, DESVIO

LADO = 256
EXT_IMAGEM = (".jpg", ".jpeg", ".png")


def carregar_checkpoint(caminho, dispositivo):
    from modelo import criar_modelo
    ck = torch.load(caminho, map_location=dispositivo)
    m = criar_modelo(ck["arquitetura"], pesos=False)
    m.load_state_dict(ck["estado"])
    m.eval().to(dispositivo)
    return m, ck


def grade_de_recortes(altura, largura, lado=LADO):
    return [(x, y) for y in range(0, altura - lado + 1, lado) for x in range(0, largura - lado + 1, lado)]


def preparar_quadro(quadro_bgr, largura_alvo=1024):
    """Ajusta a largura do quadro. Quadros pequenos são ampliados para caber ao menos 1 recorte."""
    h, w = quadro_bgr.shape[:2]
    escala = largura_alvo / w
    novo = cv2.resize(quadro_bgr, (largura_alvo, max(int(round(h * escala)), LADO)),
                      interpolation=cv2.INTER_AREA if escala < 1 else cv2.INTER_LINEAR)
    return novo


@torch.no_grad()
def classificar_quadro(m, quadro_bgr, tamanho, dispositivo, largura_alvo=1024, lote=32):
    """Devolve (quadro ajustado, lista de posições, probabilidades por recorte)."""
    quadro = preparar_quadro(quadro_bgr, largura_alvo)
    h, w = quadro.shape[:2]
    pos = grade_de_recortes(h, w)
    rgb = cv2.cvtColor(quadro, cv2.COLOR_BGR2RGB)
    media = torch.tensor(MEDIA).view(1, 3, 1, 1)
    desvio = torch.tensor(DESVIO).view(1, 3, 1, 1)
    probs = []
    for i in range(0, len(pos), lote):
        blocos = [rgb[y:y + LADO, x:x + LADO] for x, y in pos[i:i + lote]]
        x = torch.from_numpy(np.stack(blocos)).permute(0, 3, 1, 2).float() / 255.0
        if tamanho != LADO:
            x = torch.nn.functional.interpolate(x, size=(tamanho, tamanho), mode="bilinear",
                                                align_corners=False)
        x = ((x - media) / desvio).to(dispositivo)
        probs.append(torch.softmax(m(x), dim=1)[:, 1].cpu().numpy())
    return quadro, pos, (np.concatenate(probs) if probs else np.zeros(0))


def desenhar(quadro, pos, probs, limiar, texto_extra=""):
    """Marca em vermelho os recortes acima do limiar, com a confiança. Texto sem acento por causa da fonte do OpenCV."""
    saida = quadro.copy()
    for (x, y), p in zip(pos, probs):
        if p >= limiar:
            cv2.rectangle(saida, (x, y), (x + LADO, y + LADO), (0, 0, 255), 3)
            cv2.putText(saida, f"{p:.2f}", (x + 8, y + 28), cv2.FONT_HERSHEY_SIMPLEX, 0.9,
                        (0, 0, 255), 2, cv2.LINE_AA)
    pmax = float(probs.max()) if len(probs) else 0.0
    achou = pmax >= limiar
    faixa = (0, 0, 200) if achou else (60, 140, 60)
    cv2.rectangle(saida, (0, 0), (saida.shape[1], 38), faixa, -1)
    msg = f"{'POSSIVEL FISSURA' if achou else 'sem indicio'}  conf. max {pmax:.2f}  limiar {limiar:.2f} {texto_extra}"
    cv2.putText(saida, msg, (10, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2, cv2.LINE_AA)
    return saida


def analisar_imagem(m, caminho_ou_array, limiar, tamanho, dispositivo, largura_alvo=1024):
    """Uma imagem: devolve imagem desenhada (BGR) e um resumo."""
    if isinstance(caminho_ou_array, (str, Path)):
        quadro = cv2.imread(str(caminho_ou_array))
        if quadro is None:
            raise ValueError(f"Não consegui abrir a imagem {caminho_ou_array}")
    else:
        quadro = caminho_ou_array
    t0 = time.perf_counter()
    q, pos, probs = classificar_quadro(m, quadro, tamanho, dispositivo, largura_alvo)
    ms = (time.perf_counter() - t0) * 1000
    resumo = {
        "prob_max": float(probs.max()) if len(probs) else 0.0,
        "recortes": int(len(probs)),
        "recortes_positivos": int((probs >= limiar).sum()),
        "ms": round(ms, 1),
    }
    return desenhar(q, pos, probs, limiar), resumo


def _quadros(entrada, cada_n, max_quadros):
    """Gera (indice, quadro) de um vídeo ou de uma pasta com sequência de imagens."""
    entrada = Path(entrada)
    entregues = 0
    if entrada.is_dir():
        arquivos = sorted(p for p in entrada.iterdir() if p.suffix.lower() in EXT_IMAGEM)
        for i, p in enumerate(arquivos):
            if i % cada_n:
                continue
            q = cv2.imread(str(p))
            if q is not None:
                yield i, q
                entregues += 1
                if max_quadros and entregues >= max_quadros:
                    return
    else:
        cap = cv2.VideoCapture(str(entrada))
        if not cap.isOpened():
            raise ValueError(f"Não consegui abrir o vídeo {entrada}")
        i = 0
        while True:
            ok, q = cap.read()
            if not ok:
                break
            if i % cada_n == 0:
                yield i, q
                entregues += 1
                if max_quadros and entregues >= max_quadros:
                    break
            i += 1
        cap.release()


def processar_video(m, entrada, saida_video, saida_json, limiar, tamanho, dispositivo,
                    cada_n=5, largura_alvo=1024, max_quadros=None, confirmacoes=2, fps_saida=4):
    """Processa um vídeo curto ou uma sequência de imagens simulando monitoramento urbano.

    Para não gerar alerta por um quadro isolado, só conto um EVENTO quando o limiar é
    passado em `confirmacoes` quadros seguidos (entre os quadros analisados).
    """
    quadros_info, escritor, seguidos, eventos, em_evento = [], None, 0, 0, False
    tempos = []
    t_total = time.perf_counter()
    for indice, quadro in _quadros(entrada, cada_n, max_quadros):
        t0 = time.perf_counter()
        q, pos, probs = classificar_quadro(m, quadro, tamanho, dispositivo, largura_alvo)
        tempos.append(time.perf_counter() - t0)
        pmax = float(probs.max()) if len(probs) else 0.0
        positivo = pmax >= limiar
        seguidos = seguidos + 1 if positivo else 0
        novo_evento = False
        if seguidos >= confirmacoes and not em_evento:
            eventos += 1
            em_evento = True
            novo_evento = True
        if not positivo:
            em_evento = False
        quadros_info.append({
            "quadro": int(indice), "prob_max": round(pmax, 4),
            "recortes_positivos": int((probs >= limiar).sum()), "recortes": int(len(probs)),
            "positivo": bool(positivo), "novo_evento": novo_evento, "ms": round(tempos[-1] * 1000, 1),
        })
        img = desenhar(q, pos, probs, limiar, texto_extra=f"quadro {indice}")
        if escritor is None and saida_video:
            Path(saida_video).parent.mkdir(parents=True, exist_ok=True)
            escritor = cv2.VideoWriter(str(saida_video), cv2.VideoWriter_fourcc(*"mp4v"), fps_saida,
                                       (img.shape[1], img.shape[0]))
        if escritor is not None:
            escritor.write(img)
    if escritor is not None:
        escritor.release()
    total = time.perf_counter() - t_total
    resumo = {
        "entrada": str(entrada), "quadros_analisados": len(quadros_info),
        "quadros_positivos": int(sum(q["positivo"] for q in quadros_info)),
        "eventos_confirmados": eventos, "confirmacoes_exigidas": confirmacoes,
        "limiar": limiar, "largura_alvo": largura_alvo, "cada_n_quadros": cada_n,
        "ms_medio_por_quadro": round(float(np.mean(tempos) * 1000), 1) if tempos else None,
        "quadros_por_segundo": round(len(tempos) / total, 2) if tempos else None,
        "dispositivo": str(dispositivo), "quadros": quadros_info,
    }
    if saida_json:
        Path(saida_json).parent.mkdir(parents=True, exist_ok=True)
        Path(saida_json).write_text(json.dumps(resumo, ensure_ascii=False, indent=2), encoding="utf-8")
    return resumo
