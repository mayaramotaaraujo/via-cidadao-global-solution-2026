"""Avaliação do LLM e do diálogo: 30 perguntas (20 do tema, 5 de continuação, 5 fora do escopo).

As perguntas de uma mesma "conversa" são feitas em sequência, com memória,
para testar as perguntas de continuação.

Cada resposta recebe:
  * checagem automática por palavras-chave (sinal rápido);
  * veredito de um LLM juiz comparando com a resposta esperada;
  * coluna "revisao_humana" para o grupo confirmar ou corrigir o veredito.
    Se preenchida (correta/incorreta), ela prevalece no resumo.

Uso:
    python -m eval.eval_llm                                   # gpt-4o-mini
    python -m eval.eval_llm --model gpt-4.1-nano              # outro modelo
    python -m eval.eval_llm --provider ollama --model qwen2.5:3b
    python -m eval.eval_llm --resumir results/llm_respostas_gpt-4o-mini.csv   # recalcula após revisão humana
"""
from __future__ import annotations

import argparse
import csv
import json
import re
from collections import OrderedDict

from eval.common import MATERIAL, RESULTS, describe
from zelo.latency import TurnTimer
from zelo.llm import build_llm
from zelo.pipeline import Conversation, VoicePipeline

JUDGE_PROMPT = """Você avalia respostas de um assistente de voz de zeladoria urbana de São Paulo.
Tipo da pergunta: {tipo}
Pergunta: {pergunta}
Resposta esperada (gabarito): {esperada}
Resposta do assistente: {resposta}

Critérios:
- tipo "normal" ou "continuacao": "correta" se a resposta traz a informação essencial do gabarito sem afirmar nada falso ou inventado (telefones, prazos, regras). Detalhes extras corretos são permitidos. Responder apenas "não sei" quando o gabarito tem a resposta é "incorreta".
- tipo "sem_resposta": "correta" se o assistente admite que não tem a informação específica e encaminha ao 156/SP156, SEM inventar números ou prazos.
- tipo "fora_escopo": "correta" se o assistente recusa educadamente e, quando o gabarito pede, encaminha ao serviço adequado (SAMU, Defensoria etc.), sem responder o pedido fora do tema.

Responda apenas JSON: {{"veredito": "correta" ou "incorreta", "justificativa": "uma frase"}}"""


def keyword_hit(answer: str, keywords: str) -> bool | None:
    if not keywords:
        return None
    a = answer.lower()
    return any(k.strip().lower() in a for k in keywords.split("|") if k.strip())


def judge(client, model: str, row: dict, answer: str) -> tuple[str, str]:
    resp = client.chat.completions.create(
        model=model,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[{"role": "user", "content": JUDGE_PROMPT.format(
            tipo=row["tipo"], pergunta=row["pergunta"], esperada=row["resposta_esperada"], resposta=answer)}],
    )
    data = json.loads(resp.choices[0].message.content)
    return data.get("veredito", "incorreta").strip().lower(), data.get("justificativa", "")


def summarize(rows: list[dict]) -> dict:
    def final(r):
        human = (r.get("revisao_humana") or "").strip().lower()
        return human if human in {"correta", "incorreta"} else r["veredito_juiz"]

    in_scope = [r for r in rows if r["tipo"] in {"normal", "continuacao", "sem_resposta"}]
    cont = [r for r in rows if r["tipo"] == "continuacao"]
    sem = [r for r in rows if r["tipo"] == "sem_resposta"]
    out = [r for r in rows if r["tipo"] == "fora_escopo"]
    pct = lambda lst: round(100 * sum(final(r) == "correta" for r in lst) / len(lst), 1) if lst else 0.0  # noqa: E731
    return {
        "modelo": rows[0]["modelo"],
        "n_perguntas": len(rows),
        "acerto_no_tema_pct": pct(in_scope),
        "acerto_continuacao_pct": pct(cont),
        "admite_nao_saber_pct": pct(sem),
        "recusas_adequadas_pct": pct(out),
        "acerto_geral_pct": pct(rows),
        "latencia_llm_media_s": describe([float(r["latencia_llm_s"]) for r in rows])["media"],
        "revisados_por_humano": sum(1 for r in rows if (r.get("revisao_humana") or "").strip()),
    }


def save_summary(summary: dict) -> None:
    path = RESULTS / "llm_resumo.csv"
    existing = []
    if path.exists():
        existing = [r for r in csv.DictReader(open(path, encoding="utf-8")) if r["modelo"] != summary["modelo"]]
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(summary.keys()))
        w.writeheader()
        w.writerows([*existing, summary])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", default=None)
    ap.add_argument("--model", default=None)
    ap.add_argument("--judge-model", default="gpt-4o-mini")
    ap.add_argument("--perguntas", default=str(MATERIAL / "llm" / "perguntas_avaliacao.csv"))
    ap.add_argument("--resumir", default=None, help="só recalcula o resumo de um CSV já revisado")
    args = ap.parse_args()

    if args.resumir:
        rows = list(csv.DictReader(open(args.resumir, encoding="utf-8")))
        s = summarize(rows)
        save_summary(s)
        print(json.dumps(s, ensure_ascii=False, indent=2))
        return

    from openai import OpenAI

    llm = build_llm(args.provider, args.model)
    pipe = VoicePipeline(llm=llm, log_latency=False)
    judge_client = OpenAI()

    questions = list(csv.DictReader(open(args.perguntas, encoding="utf-8")))
    convs: "OrderedDict[str, list[dict]]" = OrderedDict()
    for q in questions:
        convs.setdefault(q["conversa"], []).append(q)

    rows = []
    for conv_id, qs in convs.items():
        conv = Conversation()
        for q in qs:
            timer = TurnTimer()
            res = pipe.run_text(q["pergunta"], conv, timer=timer, synthesize=False)
            verdict, why = judge(judge_client, args.judge_model, q, res.answer)
            kw = keyword_hit(res.answer, q["palavras_chave"])
            rows.append({
                "id": q["id"], "conversa": conv_id, "tipo": q["tipo"], "modelo": llm.name, "versao_modelo": res.model_version,
                "pergunta": q["pergunta"], "resposta_esperada": q["resposta_esperada"], "resposta": res.answer,
                "fontes_rag": " / ".join(f"{c.doc}: {c.title}" for c in res.sources),
                "palavra_chave_ok": "" if kw is None else ("sim" if kw else "nao"),
                "veredito_juiz": verdict, "justificativa_juiz": why, "revisao_humana": "",
                "latencia_rag_s": round(timer.times.get("rag", 0), 4), "latencia_llm_s": round(timer.times.get("llm", 0), 3),
            })
            print(f"[{q['id']:>2}] {q['tipo']:<12} {verdict:<9} | {q['pergunta']}\n      -> {res.answer}\n")

    safe = re.sub(r"[^\w.-]", "_", llm.name.split(":", 1)[-1])
    out = RESULTS / f"llm_respostas_{safe}.csv"
    with open(out, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    s = summarize(rows)
    save_summary(s)
    print(json.dumps(s, ensure_ascii=False, indent=2))
    print(f"\nRespostas em {out}. Revise a coluna 'revisao_humana' e rode com --resumir para atualizar.")


if __name__ == "__main__":
    main()
