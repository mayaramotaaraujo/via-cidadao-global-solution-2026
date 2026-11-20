"""IA do robô: classificador de NLP local (scikit-learn), sem LLM.

Por que não um LLM aqui? O robô roda em lote, todo dia, com centenas de relatos
que podem conter dados pessoais. Um modelo local:
- não envia o texto do cidadão para nenhuma API externa (LGPD);
- é gratuito, rápido (milissegundos por relato) e determinístico;
- devolve uma probabilidade, que usamos para decidir quando chamar um humano.

Modelo: TF-IDF de palavras (1 a 2 gramas) + TF-IDF de caracteres (3 a 5 gramas,
pega erros de digitação como "burako" ou "poste apagadu") + Regressão Logística.
"""

from __future__ import annotations

import logging
import unicodedata
from dataclasses import dataclass
from pathlib import Path

import joblib
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import FeatureUnion, Pipeline

log = logging.getLogger("zelo.ia")

VERSAO_MODELO = "tfidf-logreg-v1"


def preprocessar(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", str(texto).lower())
    return "".join(c for c in texto if not unicodedata.combining(c))


def criar_pipeline() -> Pipeline:
    return Pipeline([
        ("features", FeatureUnion([
            ("palavras", TfidfVectorizer(preprocessor=preprocessar, ngram_range=(1, 2),
                                         min_df=1, sublinear_tf=True)),
            ("caracteres", TfidfVectorizer(preprocessor=preprocessar, analyzer="char_wb",
                                           ngram_range=(3, 5), min_df=2, sublinear_tf=True)),
        ])),
        ("clf", LogisticRegression(max_iter=2000, C=8.0, class_weight="balanced")),
    ])


def treinar(caminho_treino: Path, caminho_modelo: Path | None = None) -> Pipeline:
    df = pd.read_csv(caminho_treino)
    modelo = criar_pipeline().fit(df["descricao"], df["categoria"])
    if caminho_modelo:
        caminho_modelo.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump({"versao": VERSAO_MODELO, "modelo": modelo}, caminho_modelo)
        log.info("Modelo treinado com %d exemplos e salvo em %s", len(df), caminho_modelo.name)
    return modelo


@dataclass
class Predicao:
    categoria: str
    confianca: float
    segunda_opcao: str


class Classificador:
    def __init__(self, modelo: Pipeline):
        self.modelo = modelo

    @classmethod
    def carregar_ou_treinar(cls, caminho_modelo: Path, caminho_treino: Path) -> "Classificador":
        """Resiliência: se o arquivo do modelo sumiu ou está corrompido, treina de novo."""
        try:
            pacote = joblib.load(caminho_modelo)
            if pacote.get("versao") != VERSAO_MODELO:
                raise ValueError(f"versão {pacote.get('versao')} diferente de {VERSAO_MODELO}")
            log.info("Modelo carregado: %s", caminho_modelo.name)
            return cls(pacote["modelo"])
        except FileNotFoundError:
            log.warning("Modelo não encontrado. Treinando a partir de %s", caminho_treino.name)
        except Exception as e:  # noqa: BLE001 - arquivo corrompido, versão antiga etc.
            log.warning("Modelo inválido (%s). Treinando novamente.", e)
        return cls(treinar(caminho_treino, caminho_modelo))

    def prever(self, textos: list[str]) -> list[Predicao]:
        if not textos:
            return []
        probas = self.modelo.predict_proba(textos)
        classes = self.modelo.classes_
        saida = []
        for linha in probas:
            ordem = linha.argsort()[::-1]
            saida.append(Predicao(classes[ordem[0]], float(linha[ordem[0]]), classes[ordem[1]]))
        return saida
