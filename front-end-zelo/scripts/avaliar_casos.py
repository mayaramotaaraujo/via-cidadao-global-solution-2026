"""Avalia a IA com casos de teste e gera uma tabela Markdown de evidências.

Uso (com a API rodando):
    python scripts/avaliar_casos.py --api http://localhost:8000
Saída: docs/validacao/resultados_casos_ia.md
"""

import argparse
import json
import time
from datetime import datetime
from pathlib import Path

import httpx

RAIZ = Path(__file__).resolve().parents[1]
CASOS = RAIZ / "docs" / "validacao" / "casos_teste_ia.json"
SAIDA = RAIZ / "docs" / "validacao" / "resultados_casos_ia.md"


def avaliar(caso: dict, obtido: dict) -> tuple[bool, list[str]]:
    falhas = []
    for campo, esperado in caso["esperado"].items():
        if campo == "pii_removida":
            ok = bool(obtido.get("dados_pessoais_removidos")) == esperado
        else:
            ok = obtido.get(campo) == esperado
        if not ok:
            falhas.append(f"{campo}: esperado `{esperado}`, obtido `{obtido.get(campo)}`")
    return not falhas, falhas


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api", default="http://localhost:8000")
    args = parser.parse_args()

    casos = json.loads(CASOS.read_text(encoding="utf-8"))
    linhas, acertos, latencias = [], 0, []
    versao = modelo = "?"
    for caso in casos:
        time.sleep(8)  # respeita o limite de análises por minuto da API
        r = httpx.post(
            f"{args.api}/api/v1/relatos/analisar",
            json={"descricao": caso["descricao"], "bairro": caso["bairro"]},
            timeout=60,
        )
        obtido = r.json()
        if r.is_error:
            linhas.append(f"| {caso['id']} | {caso['nome']} | — | ERRO {r.status_code}: {obtido} | ❌ |")
            continue
        versao, modelo = obtido["versao_prompt"], obtido["modelo"]
        latencias.append(obtido["latencia_ms"])
        ok, falhas = avaliar(caso, obtido)
        acertos += ok
        esperado = ", ".join(f"{k}={v}" for k, v in caso["esperado"].items())
        resumo = (
            f"categoria={obtido['categoria']}, urgencia={obtido['urgencia']}, "
            f"revisão={obtido['precisa_revisao_humana']}, fora_escopo={obtido['fora_do_escopo']}, "
            f"PII removida={obtido['dados_pessoais_removidos'] or 'nenhuma'}"
        )
        linhas.append(
            f"| {caso['id']} | {caso['nome']} | {esperado} | {resumo} | {'✅' if ok else '❌ ' + '; '.join(falhas)} |"
        )
        print(f"[{'OK' if ok else 'FALHOU'}] {caso['nome']}")

    media = sum(latencias) / len(latencias) if latencias else 0
    md = [
        "# Resultados dos casos de teste da IA",
        "",
        f"- Execução: {datetime.now():%d/%m/%Y %H:%M} · Modelo: `{modelo}` · Prompt: `{versao}`",
        f"- Acertos: **{acertos}/{len(casos)}** · Latência média: **{media / 1000:.1f} s**",
        "",
        "| # | Caso | Saída esperada | Saída obtida | Resultado |",
        "|---|------|----------------|--------------|-----------|",
        *linhas,
        "",
    ]
    SAIDA.write_text("\n".join(md), encoding="utf-8")
    print(f"\n{acertos}/{len(casos)} acertos · relatório em {SAIDA.relative_to(RAIZ)}")


if __name__ == "__main__":
    main()
