"""Busca nos trechos: lexical (BM25), vetorial (TF IDF com n gramas de caracteres)
e híbrida (junta as duas listas por Reciprocal Rank Fusion).

Observação honesta: o "vetorial" aqui usa TF IDF, não embeddings de rede neural,
porque o ambiente do trabalho roda sem baixar modelos. Os n gramas de caracteres
ajudam com variações de palavra (iluminação / iluminacao, buraco / buracos).
"""
import math
import re
import unicodedata
from collections import Counter

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

PARADAS = set("""a o as os um uma uns umas de do da dos das em no na nos nas por para com sem
sobre entre e ou que se qual quais como onde quando quem quanto quanta eu meu minha me nao não
é ser sao são foi tem ter ha há ao aos pelo pela pelos pelas isso isto esse essa este esta mais
muito pode posso preciso quero faco faço fazer tambem também ja já ainda so só""".split())


def normalizar(texto):
    t = unicodedata.normalize("NFD", texto.lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return t


def tokens(texto):
    palavras = re.findall(r"[a-z0-9]+", normalizar(texto))
    paradas = {normalizar(p) for p in PARADAS}
    return [p for p in palavras if p not in paradas and len(p) > 1]


class BM25:
    def __init__(self, textos, k1=1.5, b=0.75):
        self.k1, self.b = k1, b
        self.docs = [tokens(t) for t in textos]
        self.n = len(self.docs)
        self.avgdl = sum(len(d) for d in self.docs) / max(1, self.n)
        df = Counter()
        for d in self.docs:
            df.update(set(d))
        self.idf = {t: math.log(1 + (self.n - f + 0.5) / (f + 0.5)) for t, f in df.items()}
        self.tf = [Counter(d) for d in self.docs]

    def pontuar(self, consulta):
        q = tokens(consulta)
        notas = np.zeros(self.n)
        for i, tf in enumerate(self.tf):
            dl = len(self.docs[i])
            for t in q:
                if t in tf:
                    f = tf[t]
                    notas[i] += self.idf[t] * f * (self.k1 + 1) / (
                        f + self.k1 * (1 - self.b + self.b * dl / self.avgdl))
        return notas


class Vetorial:
    def __init__(self, textos):
        self.vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5),
                                   preprocessor=normalizar, sublinear_tf=True)
        self.matriz = self.vec.fit_transform(textos)

    def pontuar(self, consulta):
        q = self.vec.transform([consulta])
        return (self.matriz @ q.T).toarray().ravel()


def _ranking(notas):
    return list(np.argsort(-notas))


class Buscador:
    """modo: 'lexical', 'vetorial' ou 'hibrido'."""

    def __init__(self, chunks, modo="hibrido", rrf_k=60):
        self.chunks = chunks
        self.modo = modo
        self.rrf_k = rrf_k
        textos = [c["texto"] for c in chunks]
        self.bm25 = BM25(textos)
        self.vet = Vetorial(textos)

    def buscar(self, consulta, top_k=3):
        nb = self.bm25.pontuar(consulta)
        nv = self.vet.pontuar(consulta)
        if self.modo == "lexical":
            final = nb
        elif self.modo == "vetorial":
            final = nv
        else:
            final = np.zeros(len(self.chunks))
            for ranking in (_ranking(nb), _ranking(nv)):
                for pos, idx in enumerate(ranking):
                    final[idx] += 1.0 / (self.rrf_k + pos + 1)
        ordem = _ranking(final)[:top_k]
        achados = []
        for idx in ordem:
            c = dict(self.chunks[idx])
            c["nota"] = float(final[idx])
            c["nota_bm25"] = float(nb[idx])
            c["nota_vetorial"] = float(nv[idx])
            achados.append(c)
        return achados

    def cobertura(self, consulta, chunk):
        """Fração das palavras da pergunta (sem palavras comuns) que aparecem no trecho."""
        q = set(tokens(consulta))
        if not q:
            return 0.0
        t = set(tokens(chunk["texto"]))
        return len(q & t) / len(q)
