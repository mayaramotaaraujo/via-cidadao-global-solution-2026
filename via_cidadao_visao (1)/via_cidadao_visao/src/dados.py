"""Preparação dos dados do VIA VISÃO (SDNET2018).

A base SDNET2018 tem recortes de 256x256 pixels tirados de 230 fotos grandes.
Como vários recortes saem da mesma foto, eles são muito parecidos entre si.
Se eu sorteasse os recortes soltos, recortes vizinhos iam parar no treino e no
teste e a métrica ficaria boa demais. Por isso a divisão aqui é feita por FOTO:
todos os recortes de uma foto ficam no mesmo conjunto.

Estrutura esperada da pasta da base:
    SDNET2018/D/CD, D/UD   (D = tabuleiros de ponte)
    SDNET2018/P/CP, P/UP   (P = pavimentos)
    SDNET2018/W/CW, W/UW   (W = paredes)
Pastas que começam com C têm fissura (classe 1) e as que começam com U não têm (classe 0).
O nome do arquivo tem a forma NUMERO-NUMERO.jpg. Eu uso o primeiro número como
identificador da foto de origem. Essa regra precisa ser conferida no notebook
(a função conferir_grupos imprime quantos grupos saíram por superfície).
"""
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image

SUBPASTAS = {
    "CD": ("D", 1), "UD": ("D", 0),
    "CP": ("P", 1), "UP": ("P", 0),
    "CW": ("W", 1), "UW": ("W", 0),
}
NOMES_SUPERFICIE = {"D": "tabuleiro de ponte", "P": "pavimento", "W": "parede"}
EXTENSOES = (".jpg", ".jpeg", ".png")


def listar_imagens(raiz):
    """Percorre a pasta da base e monta uma tabela com uma linha por recorte."""
    linhas = []
    for p in Path(raiz).rglob("*"):
        if p.suffix.lower() not in EXTENSOES:
            continue
        sub = p.parent.name.upper()
        if sub not in SUBPASTAS:
            continue
        superficie, rotulo = SUBPASTAS[sub]
        prefixo = p.stem.split("-")[0]
        linhas.append({
            "caminho": str(p),
            "superficie": superficie,
            "rotulo": rotulo,
            "foto": f"{superficie}_{prefixo}",
        })
    if not linhas:
        raise FileNotFoundError(
            f"Nenhuma imagem encontrada em {raiz}. Confira se as pastas CD, UD, CP, UP, CW e UW existem.")
    return pd.DataFrame(linhas).sort_values("caminho").reset_index(drop=True)


def conferir_grupos(df):
    """Resumo para conferir se o prefixo do nome realmente separa as fotos de origem."""
    resumo = df.groupby("superficie").agg(
        recortes=("caminho", "count"),
        fotos=("foto", "nunique"),
        com_fissura=("rotulo", "sum"),
    )
    resumo["recortes_por_foto"] = (resumo["recortes"] / resumo["fotos"]).round(1)
    return resumo


def dividir_por_foto(df, proporcoes=(0.70, 0.15, 0.15), semente=42):
    """Sorteia as FOTOS (não os recortes) para treino, validação e teste, em cada superfície."""
    rng = np.random.default_rng(semente)
    mapa = {}
    for superficie, parte in df.groupby("superficie"):
        fotos = sorted(parte["foto"].unique())
        rng.shuffle(fotos)
        n = len(fotos)
        n_tr = int(round(proporcoes[0] * n))
        n_va = int(round(proporcoes[1] * n))
        if n >= 3:
            n_va = max(n_va, 1)
            n_tr = min(n_tr, n - n_va - 1)
        for i, f in enumerate(fotos):
            mapa[f] = "treino" if i < n_tr else ("validacao" if i < n_tr + n_va else "teste")
    saida = df.copy()
    saida["conjunto"] = saida["foto"].map(mapa)
    verificar_vazamento(saida)
    return saida


def verificar_vazamento(df):
    """Garante que nenhuma foto aparece em mais de um conjunto."""
    por_foto = df.groupby("foto")["conjunto"].nunique()
    repetidas = por_foto[por_foto > 1]
    if len(repetidas) > 0:
        raise ValueError(f"Vazamento: {len(repetidas)} fotos estão em mais de um conjunto.")
    return True


def amostrar(df, max_treino=12000, max_val=4000, max_teste=6000, neg_por_pos=2, semente=42):
    """Reduz a base para caber no tempo da atividade.

    Treino: fica com todos os recortes com fissura (até o limite) e uma quantidade
    de recortes sem fissura igual a neg_por_pos vezes a de com fissura.
    Validação e teste: sorteio simples mantendo a proporção natural da base, para
    que precisão e revocação reflitam o uso real.
    """
    rng = np.random.default_rng(semente)
    partes = []

    tr = df[df["conjunto"] == "treino"]
    pos = tr[tr["rotulo"] == 1]
    neg = tr[tr["rotulo"] == 0]
    n_pos = min(len(pos), int(max_treino / (1 + neg_por_pos)))
    n_neg = min(len(neg), n_pos * neg_por_pos)
    partes.append(pos.sample(n=n_pos, random_state=int(rng.integers(1e9))))
    partes.append(neg.sample(n=n_neg, random_state=int(rng.integers(1e9))))

    for nome, limite in (("validacao", max_val), ("teste", max_teste)):
        sub = df[df["conjunto"] == nome]
        if len(sub) > limite:
            sub = sub.sample(n=limite, random_state=int(rng.integers(1e9)))
        partes.append(sub)
    return pd.concat(partes).reset_index(drop=True)


def resumo_conjuntos(df):
    """Contagens por conjunto, classe e superfície, para o relatório."""
    saida = {}
    for conj, parte in df.groupby("conjunto"):
        saida[conj] = {
            "recortes": int(len(parte)),
            "fotos": int(parte["foto"].nunique()),
            "com_fissura": int(parte["rotulo"].sum()),
            "sem_fissura": int((parte["rotulo"] == 0).sum()),
            "proporcao_fissura": round(float(parte["rotulo"].mean()), 4),
            "por_superficie": {s: int(n) for s, n in parte["superficie"].value_counts().items()},
        }
    return saida


def carregar_rgb(caminho):
    return Image.open(caminho).convert("RGB")
