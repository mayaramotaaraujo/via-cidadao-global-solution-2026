"""Calcula acertos, matriz de confusão e métricas a partir das planilhas CSV.

Duas planilhas, que são duas avaliações diferentes:
  dados/teste_arquivos.csv  teste com 5 arquivos inéditos por classe (Model testing, Classify all)
  dados/ao_vivo.csv         15 tentativas ao vivo no celular (5 por classe)
Nada aqui é digitado à mão: tudo vem do que foi anotado nas planilhas.
"""
import csv
from pathlib import Path


def ler_csv(caminho):
    with open(caminho, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def preenchidas(linhas):
    return [l for l in linhas if (l.get("classe_prevista") or "").strip()]


def matriz(linhas, classes):
    previstas = list(classes) + ["incerto"]
    m = {r: {p: 0 for p in previstas} for r in classes}
    for l in linhas:
        real, prev = l["classe_real"].strip(), l["classe_prevista"].strip()
        if real not in m or prev not in m[real]:
            raise ValueError(f"Classe desconhecida na linha {l}. Use exatamente: {previstas}")
        m[real][prev] += 1
    return m


def metricas(m, classes):
    total = sum(sum(l.values()) for l in m.values())
    acertos = sum(m[c][c] for c in classes)
    por_classe = {}
    for c in classes:
        tp = m[c][c]
        fn = sum(m[c][p] for p in m[c] if p != c)
        fp = sum(m[r][c] for r in classes if r != c)
        por_classe[c] = {
            "n": tp + fn, "acertos": tp,
            "revocacao": tp / (tp + fn) if (tp + fn) else None,
            "precisao": tp / (tp + fp) if (tp + fp) else None,
        }
    return {"total": total, "acertos": acertos,
            "acuracia": acertos / total if total else None, "por_classe": por_classe}


def calcular(raiz, classes):
    saida = {"classes": classes}
    for nome, arq in (("teste", "teste_arquivos.csv"), ("ao_vivo", "ao_vivo.csv")):
        linhas = ler_csv(Path(raiz) / arq)
        usadas = preenchidas(linhas)
        info = {"linhas_total": len(linhas), "linhas_preenchidas": len(usadas), "linhas": usadas}
        if usadas:
            m = matriz(usadas, classes)
            info["matriz"] = m
            info["metricas"] = metricas(m, classes)
            if "ambiente" in classes:
                amb = [l for l in usadas if l["classe_real"].strip() == "ambiente"]
                ev = [l for l in usadas if l["classe_real"].strip() != "ambiente"]
                info["alarmes_falsos"] = sum(1 for l in amb if l["classe_prevista"].strip() in classes and l["classe_prevista"].strip() != "ambiente")
                info["incertos"] = sum(1 for l in usadas if l["classe_prevista"].strip() == "incerto")
                info["eventos_perdidos"] = sum(1 for l in ev if l["classe_prevista"].strip() == "ambiente")
                info["ambiente_n"] = len(amb)
                info["eventos_n"] = len(ev)
        saida[nome] = info
    return saida


if __name__ == "__main__":
    import json
    import sys
    raiz = sys.argv[1] if len(sys.argv) > 1 else "dados"
    params = json.loads((Path(raiz) / "params.json").read_text(encoding="utf-8"))
    r = calcular(raiz, params["classes"])
    for k in ("teste", "ao_vivo"):
        met = r[k].get("metricas")
        print(k, f"{r[k]['linhas_preenchidas']}/{r[k]['linhas_total']} linhas preenchidas",
              f"acurácia {met['acuracia']:.1%}" if met else "sem dados")
