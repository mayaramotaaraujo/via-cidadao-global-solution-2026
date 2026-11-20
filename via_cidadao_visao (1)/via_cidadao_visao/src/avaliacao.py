"""Métricas, escolha do limiar, análise de erros e medida de latência."""
import shutil
import time
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from PIL import Image
from sklearn.metrics import average_precision_score, confusion_matrix, roc_auc_score

from dados import carregar_rgb
from modelo import transformacao


def metricas(y, probs, limiar):
    y = np.asarray(y).astype(int)
    pred = (np.asarray(probs) >= limiar).astype(int)
    tn, fp, fn, tp = confusion_matrix(y, pred, labels=[0, 1]).ravel()
    tn, fp, fn, tp = int(tn), int(fp), int(fn), int(tp)
    prec = tp / (tp + fp) if (tp + fp) else 0.0
    rev = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * prec * rev / (prec + rev) if (prec + rev) else 0.0
    return {
        "limiar": float(limiar), "n": int(len(y)), "positivos": int(y.sum()),
        "precisao": round(float(prec), 4), "revocacao": round(float(rev), 4), "f1": round(float(f1), 4),
        "acuracia": round(float((tp + tn) / max(len(y), 1)), 4),
        "tn": tn, "fp": fp, "fn": fn, "tp": tp,
    }


def curvas(y, probs):
    """AUC e precisão média, que não dependem do limiar."""
    y = np.asarray(y).astype(int)
    if y.min() == y.max():
        return {"auc_roc": None, "precisao_media": None}
    return {"auc_roc": round(float(roc_auc_score(y, probs)), 4),
            "precisao_media": round(float(average_precision_score(y, probs)), 4)}


def escolher_limiar(y, probs, revocacao_minima=None):
    """Escolhe o limiar na VALIDAÇÃO.

    Sem revocacao_minima: o limiar com maior F1.
    Com revocacao_minima: o maior limiar que ainda mantém essa revocacao, porque na
    triagem deixar passar uma fissura custa mais do que mandar uma foto a mais para revisão.
    """
    grade = np.round(np.arange(0.05, 0.96, 0.01), 2)
    tabela = [metricas(y, probs, t) for t in grade]
    if revocacao_minima is not None:
        ok = [m for m in tabela if m["revocacao"] >= revocacao_minima]
        if ok:
            return max(ok, key=lambda m: (m["limiar"]))["limiar"], tabela
    melhor = max(tabela, key=lambda m: (m["f1"], -abs(m["limiar"] - 0.5)))
    return melhor["limiar"], tabela


def por_superficie(df_pred, limiar):
    saida = {}
    for sup, parte in df_pred.groupby("superficie"):
        saida[sup] = metricas(parte["rotulo"], parte["prob"], limiar)
    return saida


def exportar_erros(df_pred, limiar, pasta, por_classe=24):
    """Copia as imagens erradas (falsos positivos e falsos negativos) para olhar com calma.

    Fica no nome do arquivo a probabilidade que o modelo deu, para ver se o erro foi
    por pouco ou com muita certeza.
    """
    pasta = Path(pasta)
    for sub in ("falsos_positivos", "falsos_negativos"):
        if (pasta / sub).exists():
            shutil.rmtree(pasta / sub)
        (pasta / sub).mkdir(parents=True, exist_ok=True)
    fp = df_pred[(df_pred["rotulo"] == 0) & (df_pred["prob"] >= limiar)].sort_values("prob", ascending=False)
    fn = df_pred[(df_pred["rotulo"] == 1) & (df_pred["prob"] < limiar)].sort_values("prob")
    for nome, tab in (("falsos_positivos", fp), ("falsos_negativos", fn)):
        for _, l in tab.head(por_classe).iterrows():
            origem = Path(l["caminho"])
            destino = pasta / nome / f"p{l['prob']:.2f}_{l['superficie']}_{origem.name}"
            shutil.copy(origem, destino)
    return {"falsos_positivos": int(len(fp)), "falsos_negativos": int(len(fn))}


def distribuicao_erros(df_pred, limiar):
    """Quantos erros foram 'por pouco' (probabilidade perto do limiar) e quantos foram com certeza."""
    erro = df_pred[((df_pred["prob"] >= limiar).astype(int)) != df_pred["rotulo"]]
    if erro.empty:
        return {"total": 0, "perto_do_limiar": 0, "com_certeza": 0}
    dist = (erro["prob"] - limiar).abs()
    return {"total": int(len(erro)), "perto_do_limiar": int((dist <= 0.15).sum()),
            "com_certeza": int((dist > 0.35).sum())}


@torch.no_grad()
def medir_latencia(m, df, tamanho, dispositivo, n=100, aquecimento=10, lote_grande=32):
    """Mede o tempo por imagem de ponta a ponta (abrir, redimensionar, rodar a rede).

    Faz a medida com uma imagem por vez, que é o caso do uso na tela, e também com
    lote para ver a vazão máxima. Informa dispositivo e resolução.
    """
    m.eval().to(dispositivo)
    tf = transformacao(tamanho, False)
    caminhos = df["caminho"].sample(n=min(n + aquecimento, len(df)), random_state=0).tolist()
    sincronizar = (lambda: torch.cuda.synchronize()) if dispositivo.type == "cuda" else (lambda: None)

    pre, rede, total = [], [], []
    for i, c in enumerate(caminhos):
        t0 = time.perf_counter()
        x = tf(carregar_rgb(c)).unsqueeze(0).to(dispositivo)
        sincronizar()
        t1 = time.perf_counter()
        m(x)
        sincronizar()
        t2 = time.perf_counter()
        if i >= aquecimento:
            pre.append(t1 - t0)
            rede.append(t2 - t1)
            total.append(t2 - t0)
    total_ms = np.array(total) * 1000

    tensores = torch.stack([tf(carregar_rgb(c)) for c in caminhos[:lote_grande]]).to(dispositivo)
    m(tensores)
    sincronizar()
    t0 = time.perf_counter()
    for _ in range(3):
        m(tensores)
    sincronizar()
    vazao = 3 * len(tensores) / (time.perf_counter() - t0)

    return {
        "dispositivo": str(dispositivo),
        "nome_dispositivo": torch.cuda.get_device_name(0) if dispositivo.type == "cuda" else "CPU",
        "threads_cpu": int(torch.get_num_threads()),
        "resolucao_entrada": f"{tamanho}x{tamanho}",
        "imagens_medidas": int(len(total)),
        "ms_pre_processamento": round(float(np.mean(pre) * 1000), 2),
        "ms_rede": round(float(np.mean(rede) * 1000), 2),
        "ms_por_imagem": round(float(total_ms.mean()), 2),
        "ms_p95": round(float(np.percentile(total_ms, 95)), 2),
        "fps_uma_imagem": round(float(1000 / total_ms.mean()), 1),
        "fps_em_lote": round(float(vazao), 1),
    }
