"""Gera docs/anexo_registro_de_testes.md a partir de results/resultados_extrativo.json.
Assim o registro (pergunta, trechos, resposta, julgamento) vem direto da execução, sem digitar à mão."""
import json
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
r = json.loads((RAIZ / "results" / "resultados_extrativo.json").read_text(encoding="utf-8"))

L = ["# Anexo, registro dos testes", "",
     "Gerado automaticamente por src/gerar_anexo.py a partir de results/resultados_extrativo.json.",
     "Modo de geração usado: " + r["geracao"] + ".", "",
     "## Fluxo completo, conjunto de teste", ""]
for l in r["fim_a_fim"]["linhas"]:
    L += [f"### {l['id']} ({l['tipo']})", "",
          f"Pergunta: {l['pergunta']}", "",
          f"Comportamento esperado: {l['esperado']}. Resultado: {l['status']}. Julgamento: {'certo' if l['ok'] else 'errado'}.", "",
          f"Trechos recuperados: {', '.join(l['trechos']) or 'nenhum'}. Cobertura do melhor trecho: {l['cobertura']}.", "",
          "Resposta dada:", "", "```", l["resposta"], "```", ""]
L += ["## Testes de segurança", ""]
for s in r["seguranca"]:
    L += [f"### {s['id']} ({s['tipo']})", "",
          f"Pergunta: {s['pergunta']}", "",
          f"Resultado: {s['status']}. Trechos removidos por suspeita: {s['removidos_por_suspeita'] or 'nenhum'}. "
          f"Texto proibido que apareceu: {s['vazou'] or 'nenhum'}. Julgamento: {'passou' if s['passou'] else 'falhou'}.", "",
          "Resposta dada:", "", "```", s["resposta"], "```", ""]
L += ["## Gerador com contexto controlado", ""]
for d in r["gerador"]["detalhes"]:
    L += [f"### {d['id']}", "",
          f"Fatos esperados presentes: {d['fatos_encontrados']}. Citação válida: {d['citacao_valida']}.", "",
          "```", d["resposta"], "```", ""]
(RAIZ / "docs").mkdir(exist_ok=True)
(RAIZ / "docs" / "anexo_registro_de_testes.md").write_text("\n".join(L), encoding="utf-8")
print("anexo gerado")
