"""Saídas do robô: planilhas de despacho, fila de revisão humana e relatório."""

from __future__ import annotations

import json
import unicodedata
from pathlib import Path

import pandas as pd
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter

ROTULO_CATEGORIA = {
    "buraco_pavimentacao": "Buraco / pavimentação",
    "iluminacao_publica": "Iluminação pública",
    "calcada_acessibilidade": "Calçada / acessibilidade",
    "alagamento_drenagem": "Alagamento / drenagem",
    "lixo_entulho": "Lixo / entulho",
    "arvore_poda": "Árvore / poda",
    "sinalizacao_transito": "Sinalização de trânsito",
    "outros": "Outros",
}
def _ascii(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c))


ROTULO_URGENCIA = {"critica": "CRÍTICA", "alta": "Alta", "media": "Média", "baixa": "Baixa"}
_COR_URGENCIA = {"CRÍTICA": "F8B4B4", "Alta": "FCD9A8", "Média": "FFF3B0", "Baixa": "D9EAD3"}


def _tabela(linhas: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(linhas)
    if df.empty:
        return df
    return pd.DataFrame({
        "Protocolo": df["protocolo"],
        "Urgência": df["urgencia"].map(ROTULO_URGENCIA),
        "Prazo de referência (dias)": df["prazo_dias"],
        "Categoria": df["categoria"].map(ROTULO_CATEGORIA),
        "Bairro": df["bairro"],
        "Relato (anonimizado)": df["descricao_anonimizada"],
        "Por que essa urgência": df["justificativa"],
        "Confiança da IA": df["confianca"].map(lambda v: f"{v:.0%}" if pd.notna(v) else ""),
        "Canal": df["canal"],
        "Recebido em": df["recebido_em"],
    })


def _salvar_excel(df: pd.DataFrame, caminho: Path, aba: str) -> Path:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(caminho, engine="openpyxl") as w:
        df.to_excel(w, index=False, sheet_name=aba)
        ws = w.sheets[aba]
        ws.freeze_panes = "A2"
        for celula in ws[1]:
            celula.font = Font(bold=True)
        for i, coluna in enumerate(df.columns, start=1):
            maior = max([len(str(coluna))] + [len(str(v)) for v in df[coluna].head(200)])
            ws.column_dimensions[get_column_letter(i)].width = min(max(12, maior + 2), 70)
        if "Urgência" in df.columns:
            col = list(df.columns).index("Urgência") + 1
            for linha in range(2, len(df) + 2):
                cel = ws.cell(row=linha, column=col)
                cor = _COR_URGENCIA.get(cel.value)
                if cor:
                    cel.fill = PatternFill("solid", fgColor=cor)
    return caminho


def gerar_despachos(linhas: list[dict], pasta: Path) -> dict[str, tuple[Path, int, int]]:
    """Uma planilha por órgão. Retorna {órgão: (arquivo, total, críticos)}."""
    saida: dict[str, tuple[Path, int, int]] = {}
    por_orgao: dict[str, list[dict]] = {}
    for l in linhas:
        por_orgao.setdefault(l["orgao"], []).append(l)
    for orgao, itens in sorted(por_orgao.items()):
        nome = "".join(c if c.isascii() and c.isalnum() else "_" for c in _ascii(orgao)).strip("_")
        while "__" in nome:
            nome = nome.replace("__", "_")
        caminho = _salvar_excel(_tabela(itens), pasta / f"despacho_{nome}.xlsx", "Despacho")
        criticos = sum(1 for i in itens if i["urgencia"] == "critica")
        saida[orgao] = (caminho, len(itens), criticos)
    return saida


def gerar_revisao(linhas: list[dict], pasta: Path) -> Path | None:
    if not linhas:
        return None
    df = _tabela(linhas)
    df.insert(1, "Motivo da revisão", [l["motivos_revisao"] for l in linhas])
    df.insert(2, "Sugestão da IA (2ª opção)", [ROTULO_CATEGORIA.get(l.get("segunda_opcao", ""), "") for l in linhas])
    df["Categoria correta (preencher)"] = ""
    df["Decisão do servidor (preencher)"] = ""
    return _salvar_excel(df, pasta / "revisao_humana.xlsx", "Revisão humana")


def gerar_relatorio(resumo: dict, pasta: Path) -> Path:
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / "relatorio_execucao.json").write_text(
        json.dumps(resumo, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    c = resumo["contagens"]
    md = [
        f"# Relatório de execução do robô Zelo: {resumo['run_id']}",
        "",
        f"- Status: **{resumo['status']}**",
        f"- Início: {resumo['inicio']}  |  Fim: {resumo['fim']}  |  Duração: {resumo['duracao_s']:.1f} s",
        f"- Modo de e-mail: {resumo['email_modo']}",
        "",
        "## Números da execução",
        "",
        "| Etapa | Quantidade |",
        "|---|---|",
        f"| Linhas lidas (todos os canais) | {c['lidos']} |",
        f"| Enviadas para quarentena (dado inválido) | {c['quarentena']} |",
        f"| Duplicadas no próprio lote | {c['duplicados_no_lote']} |",
        f"| Já processadas em execuções anteriores | {c['ja_processados']} |",
        f"| **Novas solicitações registradas** | **{c['novos']}** |",
        f"| Encaminhadas automaticamente | {c['encaminhados']} |",
        f"| Na fila de revisão humana | {c['revisao_humana']} |",
        f"| Dados pessoais removidos de relatos | {c['com_dados_removidos']} |",
        "",
        "## Integrações",
        "",
        "| Integração | Situação |",
        "|---|---|",
    ]
    md += [f"| {k} | {v} |" for k, v in resumo["integracoes"].items()]
    md += ["", "## Arquivos de entrada", ""]
    md += [f"- OK: {a}" for a in resumo["arquivos"]["ok"]] or ["- (nenhum)"]
    md += [f"- **Rejeitado:** {a}" for a in resumo["arquivos"]["com_erro"]]
    md += [f"- Canal sem arquivo hoje: {a}" for a in resumo["arquivos"]["canais_sem_arquivo"]]

    if resumo["por_urgencia"]:
        md += ["", "## Novas solicitações por urgência", "", "| Urgência | Qtde |", "|---|---|"]
        md += [f"| {ROTULO_URGENCIA[k]} | {v} |" for k, v in resumo["por_urgencia"].items()]
    if resumo["por_orgao"]:
        md += ["", "## Despacho por órgão", "", "| Órgão | Itens | Críticos |", "|---|---|---|"]
        md += [f"| {o} | {d['itens']} | {d['criticos']} |" for o, d in resumo["por_orgao"].items()]
    if resumo["revisao"]:
        md += ["", "## Fila de revisão humana", "", "| Protocolo | Motivo |", "|---|---|"]
        md += [f"| {r['protocolo']} | {r['motivo']} |" for r in resumo["revisao"]]
    if resumo["quarentena"]:
        md += ["", "## Quarentena", "", "| Canal | Id de origem | Motivo |", "|---|---|---|"]
        md += [f"| {q['canal']} | {q['id_origem'] or '?'} | {q['motivo']} |" for q in resumo["quarentena"]]
    md += ["", "## E-mails", "", "| Situação | Qtde |", "|---|---|"]
    md += [f"| {k} | {v} |" for k, v in resumo["emails"].items()]
    if resumo["alertas"]:
        md += ["", "## Alertas", ""] + [f"- {a}" for a in resumo["alertas"]]
    md.append("")

    caminho = pasta / "relatorio_execucao.md"
    caminho.write_text("\n".join(md), encoding="utf-8")
    return caminho
