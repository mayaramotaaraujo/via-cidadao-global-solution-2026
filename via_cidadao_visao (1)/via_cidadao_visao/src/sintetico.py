"""Dados falsos, só para testar se o código roda sem baixar a base real.

Os números obtidos com esses dados NÃO valem para o relatório. Servem apenas para
mostrar que o fluxo inteiro funciona de ponta a ponta.
"""
from pathlib import Path

import cv2
import numpy as np


def _textura(rng, lado=256):
    base = rng.integers(90, 170)
    img = rng.normal(base, 12, (lado, lado)).astype(np.float32)
    img = cv2.GaussianBlur(img, (0, 0), 1.2)
    return np.clip(np.stack([img] * 3, axis=-1), 0, 255).astype(np.uint8)


def _com_fissura(rng, lado=256):
    img = _textura(rng, lado)
    x, y = int(rng.integers(20, lado - 20)), int(rng.integers(0, 30))
    for _ in range(int(rng.integers(6, 12))):
        nx = int(np.clip(x + rng.integers(-18, 18), 0, lado - 1))
        ny = int(np.clip(y + rng.integers(15, 35), 0, lado - 1))
        cv2.line(img, (x, y), (nx, ny), (25, 25, 25), int(rng.integers(1, 4)))
        x, y = nx, ny
    return img


def criar_base_falsa(raiz, fotos_por_superficie=12, recortes_por_foto=10, semente=0):
    """Cria pastas D/CD, D/UD, P/CP, P/UP, W/CW, W/UW com nomes NUMERO-NUMERO.jpg."""
    rng = np.random.default_rng(semente)
    raiz = Path(raiz)
    for sup in "DPW":
        for foto in range(fotos_por_superficie):
            id_foto = 7000 + (ord(sup) % 10) * 100 + foto
            for r in range(recortes_por_foto):
                tem = rng.random() < 0.3
                pasta = raiz / sup / (("C" if tem else "U") + sup)
                pasta.mkdir(parents=True, exist_ok=True)
                img = _com_fissura(rng) if tem else _textura(rng)
                cv2.imwrite(str(pasta / f"{id_foto}-{r + 1}.jpg"), img)
    return raiz


def criar_sequencia_falsa(pasta, quadros=12, largura=1024, altura=512, semente=1):
    """Sequência de imagens grandes, algumas com fissura, para testar o processamento de vídeo."""
    rng = np.random.default_rng(semente)
    pasta = Path(pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    for i in range(quadros):
        img = np.concatenate([np.concatenate([_textura(rng) for _ in range(largura // 256)], axis=1)
                              for _ in range(altura // 256)], axis=0)
        if 4 <= i <= 8:
            bloco = _com_fissura(rng)
            img[256:512, 256:512] = bloco
        cv2.imwrite(str(pasta / f"quadro_{i:03d}.jpg"), img)
    return pasta
