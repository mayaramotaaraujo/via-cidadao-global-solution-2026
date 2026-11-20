"""Modelos e treino do VIA VISÃO.

Uso transferência de aprendizado: pego uma rede já treinada na ImageNet e troco
só a última camada para duas classes (sem fissura, com fissura). Comparo duas
redes pequenas: MobileNetV3 small (rápida, boa para celular e borda) e ResNet18
(maior, costuma ser mais precisa).
"""
import copy
import time

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, Dataset
from torchvision import models, transforms

from dados import carregar_rgb

MEDIA = [0.485, 0.456, 0.406]
DESVIO = [0.229, 0.224, 0.225]
ARQUITETURAS = ("mobilenet_v3_small", "resnet18")


def escolher_dispositivo():
    return torch.device("cuda" if torch.cuda.is_available() else "cpu")


def transformacao(tamanho, treino):
    base = [transforms.Resize((tamanho, tamanho))]
    if treino:
        # Espelhamentos e variação de brilho e contraste, para o modelo não se prender
        # a sombra e iluminação, que são fontes de erro citadas pelo professor.
        base += [transforms.RandomHorizontalFlip(), transforms.RandomVerticalFlip(),
                 transforms.ColorJitter(brightness=0.3, contrast=0.3)]
    base += [transforms.ToTensor(), transforms.Normalize(MEDIA, DESVIO)]
    return transforms.Compose(base)


class ImagensDataset(Dataset):
    def __init__(self, df, tamanho, treino=False):
        self.caminhos = df["caminho"].tolist()
        self.rotulos = df["rotulo"].astype(int).tolist()
        self.tf = transformacao(tamanho, treino)

    def __len__(self):
        return len(self.caminhos)

    def __getitem__(self, i):
        return self.tf(carregar_rgb(self.caminhos[i])), self.rotulos[i]


def criar_modelo(nome, pesos=True):
    """pesos=False só existe para testar o código sem baixar nada."""
    if nome == "mobilenet_v3_small":
        m = models.mobilenet_v3_small(
            weights=models.MobileNet_V3_Small_Weights.DEFAULT if pesos else None)
        m.classifier[3] = nn.Linear(m.classifier[3].in_features, 2)
    elif nome == "resnet18":
        m = models.resnet18(weights=models.ResNet18_Weights.DEFAULT if pesos else None)
        m.fc = nn.Linear(m.fc.in_features, 2)
    else:
        raise ValueError(f"Arquitetura desconhecida: {nome}")
    return m


def contar_parametros(m):
    return int(sum(p.numel() for p in m.parameters()))


@torch.no_grad()
def prever_probs(m, df, tamanho, dispositivo, lote=64, workers=2):
    """Probabilidade da classe 'com fissura' para cada linha da tabela."""
    m.eval().to(dispositivo)
    dl = DataLoader(ImagensDataset(df, tamanho, False), batch_size=lote, num_workers=workers)
    saida = []
    for x, _ in dl:
        p = torch.softmax(m(x.to(dispositivo)), dim=1)[:, 1]
        saida.append(p.cpu().numpy())
    return np.concatenate(saida) if saida else np.zeros(0)


def f1_simples(y, pred):
    tp = int(((y == 1) & (pred == 1)).sum())
    fp = int(((y == 0) & (pred == 1)).sum())
    fn = int(((y == 1) & (pred == 0)).sum())
    return 2 * tp / max(2 * tp + fp + fn, 1)


def treinar(m, df_treino, df_val, tamanho, dispositivo, epocas=4, lote=32, lr=3e-4,
            workers=2, log=print):
    """Treina e devolve o modelo com o melhor F1 na validação, mais o histórico."""
    m.to(dispositivo)
    y = df_treino["rotulo"].to_numpy()
    n_pos, n_neg = max(int((y == 1).sum()), 1), max(int((y == 0).sum()), 1)
    # Peso maior para a classe rara, para o erro em fissura pesar mais.
    pesos = torch.tensor([1.0, n_neg / n_pos], dtype=torch.float32)
    pesos = pesos / pesos.sum() * 2
    perda = nn.CrossEntropyLoss(weight=pesos.to(dispositivo))
    otim = torch.optim.AdamW(m.parameters(), lr=lr, weight_decay=1e-4)
    dl = DataLoader(ImagensDataset(df_treino, tamanho, True), batch_size=lote,
                    shuffle=True, num_workers=workers)
    y_val = df_val["rotulo"].to_numpy()
    historico, melhor, melhor_f1 = [], None, -1.0
    for ep in range(1, epocas + 1):
        m.train()
        t0, soma, n = time.time(), 0.0, 0
        for x, r in dl:
            x, r = x.to(dispositivo), r.to(dispositivo)
            otim.zero_grad()
            l = perda(m(x), r)
            l.backward()
            otim.step()
            soma += l.item() * len(r)
            n += len(r)
        probs = prever_probs(m, df_val, tamanho, dispositivo, workers=workers)
        f1 = f1_simples(y_val, (probs >= 0.5).astype(int))
        historico.append({"epoca": ep, "perda_treino": soma / max(n, 1),
                          "f1_validacao_limiar_0_5": f1, "segundos": time.time() - t0})
        log(f"época {ep}/{epocas}  perda {soma / max(n, 1):.4f}  F1 val {f1:.4f}  "
            f"({time.time() - t0:.0f}s)")
        if f1 > melhor_f1:
            melhor_f1, melhor = f1, copy.deepcopy(m.state_dict())
    m.load_state_dict(melhor)
    return m, historico
