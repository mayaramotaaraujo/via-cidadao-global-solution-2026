"""Roda todos os testes da disciplina e grava results/resultados.json e results/tabelas.md.

Uso: python src/avaliar.py [--geracao extrativo|llm]
"""
import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))

from chunking import CONFIGS, carregar_corpus  # noqa: E402
from gerador import gerar_extrativo  # noqa: E402
from pipeline import Assistente  # noqa: E402
from retriever import Buscador, normalizar  # noqa: E402

PERGUNTAS = json.loads((RAIZ / "tests" / "perguntas.json").read_text(encoding="utf-8"))
CORPUS = RAIZ / "data" / "corpus"


def tem_fato(texto, fato):
    return normalizar(fato) in normalizar(texto)


def esperado_ok(p, status):
    e = p["esperado"]
    if e == "responder":
        return status in ("respondida", "emergencia")
    if e == "abster":
        return status == "abstencao"
    if e == "esclarecer":
        return status == "esclarecer"
    if e == "bloquear":
        return status == "bloqueada"
    return True


# ---------------------------------------------------------------- 1. chunking e recuperação
def avaliar_recuperacao():
    alvo = [p for p in PERGUNTAS if p["conjunto"] == "teste" and p["docs_esperados"] and not p.get("historico")]
    linhas = []
    for nome, cfg in CONFIGS.items():
        chunks = carregar_corpus(CORPUS, cfg)
        for modo in ("lexical", "vetorial", "hibrido"):
            b = Buscador(chunks, modo=modo)
            h1 = h3 = rr = ev3 = ev5 = 0
            for p in alvo:
                achados = b.buscar(p["pergunta"], top_k=5)
                docs = [a["doc_id"] for a in achados[:3]]
                esperados = set(p["docs_esperados"])
                if docs and docs[0] in esperados:
                    h1 += 1
                if any(d in esperados for d in docs):
                    h3 += 1
                for pos, d in enumerate(docs):
                    if d in esperados:
                        rr += 1 / (pos + 1)
                        break
                # evidência: algum trecho recuperado contém o fato que responde a pergunta?
                ev3 += any(all(tem_fato(a["texto"], f) for f in p["fatos"]) for a in achados[:3])
                ev5 += any(all(tem_fato(a["texto"], f) for f in p["fatos"]) for a in achados[:5])
            n = len(alvo)
            linhas.append({"config": nome, "busca": modo, "n_trechos": len(chunks), "perguntas": n,
                           "hit_at_1": round(h1 / n, 2), "hit_at_3": round(h3 / n, 2), "mrr": round(rr / n, 2),
                           "evidencia_top3": round(ev3 / n, 2), "evidencia_top5": round(ev5 / n, 2)})
    return linhas


def erros_recuperacao():
    """Quais perguntas a configuração escolhida errou no top 3."""
    chunks = carregar_corpus(CORPUS, CONFIGS["C_estrutural_700_overlap_1frase"])
    b = Buscador(chunks, modo="hibrido")
    erros = []
    for p in PERGUNTAS:
        if p["conjunto"] == "teste" and p["docs_esperados"] and not p.get("historico"):
            achados = b.buscar(p["pergunta"], top_k=3)
            docs = [a["doc_id"] for a in achados]
            if not any(d in p["docs_esperados"] for d in docs[:3]) or docs[0] not in p["docs_esperados"]:
                erros.append({"id": p["id"], "pergunta": p["pergunta"], "esperado": p["docs_esperados"],
                              "recuperado": [f"{a['id']} ({a['secao']})" for a in achados]})
    return erros


# ---------------------------------------------------------------- 2. gerador com contexto controlado
def avaliar_gerador():
    chunks = carregar_corpus(CORPUS, CONFIGS["C_estrutural_700_overlap_1frase"])
    por_doc = {}
    for c in chunks:
        por_doc.setdefault(c["doc_id"], []).append(c)
    resp = [p for p in PERGUNTAS if p["conjunto"] == "teste" and p["docs_esperados"] and not p.get("historico")]
    detalhes, fatos_ok, fatos_tot, cit_ok = [], 0, 0, 0
    for p in resp:
        ctx = [c for d in p["docs_esperados"] for c in por_doc[d]]
        texto = gerar_extrativo(p["pergunta"], ctx) or ""
        achou = [tem_fato(texto, f) for f in p["fatos"]]
        fatos_ok += sum(achou)
        fatos_tot += len(achou)
        ids_citados = {x.strip("[]") for x in texto.split() if x.startswith("[") and x.endswith("]")}
        valido = bool(ids_citados) and ids_citados <= set(p["docs_esperados"])
        cit_ok += valido
        detalhes.append({"id": p["id"], "fatos_encontrados": achou, "citacao_valida": valido, "resposta": texto})
    # contexto errado de propósito: o gerador sozinho reconhece falta de evidência?
    sem = [p for p in PERGUNTAS if p["conjunto"] == "teste" and p["tipo"] in ("sem_resposta", "fora_de_escopo")]
    contexto_errado = por_doc["f08"]
    devolveu_algo = sum(1 for p in sem if gerar_extrativo(p["pergunta"], contexto_errado))
    return {"perguntas_com_contexto_certo": len(resp), "fatos_esperados_presentes": f"{fatos_ok}/{fatos_tot}",
            "citacoes_validas": f"{cit_ok}/{len(resp)}",
            "sem_evidencia_testadas": len(sem), "gerador_sozinho_ainda_respondeu": devolveu_algo,
            "detalhes": detalhes}


# ---------------------------------------------------------------- 3. calibragem do limiar (só conjunto de desenvolvimento)
def varrer_limiar():
    dev = [p for p in PERGUNTAS if p["conjunto"] == "desenvolvimento"]
    saida = []
    for lim in (0.15, 0.20, 0.25, 0.30, 0.34, 0.40, 0.50, 0.60):
        a = Assistente(limiar=lim)
        ok = sum(esperado_ok(p, a.responder(p["pergunta"])["status"]) for p in dev)
        saida.append({"limiar": lim, "acertos_dev": f"{ok}/{len(dev)}"})
    return saida


# ---------------------------------------------------------------- 4. fluxo completo
def avaliar_fim_a_fim(modo_geracao):
    a = Assistente(modo_geracao=modo_geracao)
    alvo = [p for p in PERGUNTAS if p["conjunto"] == "teste"]
    linhas, acertos = [], 0
    respondeu_sem_base = 0
    abstencao_indevida = 0
    n_responder = sum(1 for p in alvo if p["esperado"] == "responder")
    n_sem_base = sum(1 for p in alvo if p["esperado"] == "abster")
    fatos_ok = fatos_tot = 0
    for p in alvo:
        r = a.responder(p["pergunta"], p.get("historico"))
        ok = esperado_ok(p, r["status"])
        if p.get("exige_emergencia"):
            ok = ok and r["status"] == "emergencia"
        acertos += ok
        if p["esperado"] == "abster" and r["status"] in ("respondida", "emergencia"):
            respondeu_sem_base += 1
        if p["esperado"] == "responder" and r["status"] == "abstencao":
            abstencao_indevida += 1
        if p["esperado"] == "responder" and r["status"] in ("respondida", "emergencia"):
            for f in p["fatos"]:
                fatos_tot += 1
                fatos_ok += tem_fato(r["resposta"], f)
        linhas.append({"id": p["id"], "tipo": p["tipo"], "pergunta": p["pergunta"], "esperado": p["esperado"],
                       "status": r["status"], "ok": bool(ok), "cobertura": r.get("cobertura_melhor"),
                       "trechos": [t["id"] for t in r["trechos"]], "resposta": r["resposta"]})
    return {"total": len(alvo), "comportamento_correto": acertos,
            "respondeu_sem_base": f"{respondeu_sem_base}/{n_sem_base}",
            "abstencao_indevida": f"{abstencao_indevida}/{n_responder}",
            "fatos_esperados_nas_respostas": f"{fatos_ok}/{fatos_tot}", "linhas": linhas}


# ---------------------------------------------------------------- 5. segurança
def avaliar_seguranca(modo_geracao):
    saida = []
    for p in [x for x in PERGUNTAS if x["conjunto"] == "seguranca"]:
        pasta = CORPUS
        tmp = None
        if p.get("corpus"):
            tmp = tempfile.mkdtemp()
            for f in CORPUS.glob("*.md"):
                shutil.copy(f, tmp)
            for f in (RAIZ / p["corpus"]).glob("*.md"):
                shutil.copy(f, tmp)
            pasta = Path(tmp)
        a = Assistente(pasta_corpus=pasta, modo_geracao=modo_geracao)
        r = a.responder(p["pergunta"])
        vazou = [x for x in p.get("nao_pode_conter", []) if x in r["resposta"]]
        ok = esperado_ok(p, r["status"]) and not vazou
        saida.append({"id": p["id"], "tipo": p["tipo"], "pergunta": p["pergunta"], "status": r["status"],
                      "removidos_por_suspeita": r["removidos_por_suspeita"], "vazou": vazou,
                      "passou": bool(ok), "resposta": r["resposta"]})
        if tmp:
            shutil.rmtree(tmp, ignore_errors=True)
    return saida


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--geracao", default="extrativo", choices=["extrativo", "llm"])
    args = ap.parse_args()
    resultado = {
        "geracao": args.geracao,
        "recuperacao": avaliar_recuperacao(),
        "erros_recuperacao_config_escolhida": erros_recuperacao(),
        "gerador": avaliar_gerador(),
        "limiar": varrer_limiar(),
        "fim_a_fim": avaliar_fim_a_fim(args.geracao),
        "seguranca": avaliar_seguranca(args.geracao),
    }
    (RAIZ / "results").mkdir(exist_ok=True)
    (RAIZ / "results" / f"resultados_{args.geracao}.json").write_text(
        json.dumps(resultado, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in resultado.items() if k not in ("fim_a_fim", "seguranca", "gerador")},
                     ensure_ascii=False, indent=1))
    fa = resultado["fim_a_fim"]
    print("FIM A FIM:", {k: v for k, v in fa.items() if k != "linhas"})
    for l in fa["linhas"]:
        print(l["id"], l["esperado"], "->", l["status"], "OK" if l["ok"] else "ERRO", "cob", l["cobertura"], l["trechos"])
    g = resultado["gerador"]
    print("GERADOR:", {k: v for k, v in g.items() if k != "detalhes"})
    for s in resultado["seguranca"]:
        print(s["id"], s["status"], "PASSOU" if s["passou"] else "FALHOU", s["removidos_por_suspeita"], s["vazou"])
