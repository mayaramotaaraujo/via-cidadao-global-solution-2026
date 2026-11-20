"""Regras determinísticas aplicadas DEPOIS da IA (guarda-corpos).

Decisão de projeto: a IA interpreta o texto (categoria, urgência, resumo).
Já informações institucionais — qual órgão atende e em quanto tempo — vêm
desta tabela fixa, porque um LLM pode "alucinar" nomes de órgãos ou prazos.
"""

from app.schemas.relato import AnaliseLLM, Categoria, ContextoClima, Urgencia

ORGAOS: dict[Categoria, str] = {
    Categoria.BURACO: "Subprefeitura da região (manutenção viária)",
    Categoria.ILUMINACAO: "Departamento de Iluminação Pública (ILUME)",
    Categoria.CALCADA: "Subprefeitura da região (calçadas e acessibilidade)",
    Categoria.ALAGAMENTO: "Subprefeitura da região (drenagem)",
    Categoria.LIXO: "SP Regula (limpeza urbana)",
    Categoria.ARVORE: "Subprefeitura da região (manejo arbóreo)",
    Categoria.SINALIZACAO: "CET – Companhia de Engenharia de Tráfego",
    Categoria.OUTROS: "Central de atendimento SP156 (triagem manual)",
}

# Prazos de REFERÊNCIA do protótipo (não são prazos oficiais da Prefeitura).
PRAZOS: dict[Urgencia, int] = {
    Urgencia.CRITICA: 1,
    Urgencia.ALTA: 3,
    Urgencia.MEDIA: 10,
    Urgencia.BAIXA: 30,
}

LIMIAR_CONFIANCA = 0.6
LIMIAR_CHUVA_FORTE_MM = 20.0

# Termos que, se presentes, exigem que um humano confira a urgência
# caso a IA tenha classificado abaixo de "alta".
_TERMOS_RISCO = (
    "fio", "fiação", "choque", "faísca", "faisca", "desab", "caindo", "caiu em cima",
    "ilhad", "arrastad", "criança caiu", "acidente", "ferid",
)


def aplicar_regras(
    analise: AnaliseLLM, descricao: str, clima: ContextoClima | None
) -> tuple[AnaliseLLM, list[str], list[str]]:
    """Retorna (analise_ajustada, ajustes_aplicados, motivos_para_revisao_humana)."""
    ajustes: list[str] = []
    motivos: list[str] = []
    urgencia = analise.urgencia
    confianca = max(0.0, min(1.0, analise.confianca))

    # 1) Risco imediato nunca pode ter urgência baixa/média.
    if analise.risco_imediato and urgencia.nivel < Urgencia.ALTA.nivel:
        urgencia = Urgencia.ALTA
        ajustes.append("Urgência elevada para ALTA porque a IA identificou risco imediato.")

    # 2) Cruzamento com dados abertos: chuva forte + alagamento/árvore.
    if (
        clima
        and clima.chuva_prevista_mm >= LIMIAR_CHUVA_FORTE_MM
        and analise.categoria in (Categoria.ALAGAMENTO, Categoria.ARVORE)
        and urgencia != Urgencia.CRITICA
    ):
        urgencia = Urgencia.de_nivel(urgencia.nivel + 1)
        ajustes.append(
            f"Urgência elevada para {urgencia.value.upper()}: previsão de {clima.chuva_prevista_mm:.0f} mm de chuva hoje."
        )

    # 3) Quando pedir revisão humana.
    if confianca < LIMIAR_CONFIANCA:
        motivos.append("A IA teve pouca certeza na classificação.")
    if analise.fora_do_escopo:
        motivos.append("O relato parece não ser um problema de zeladoria urbana.")
    if analise.categoria == Categoria.OUTROS and not analise.fora_do_escopo:
        motivos.append("O problema não se encaixou em nenhuma categoria conhecida.")
    texto = descricao.lower()
    if urgencia.nivel < Urgencia.ALTA.nivel and any(t in texto for t in _TERMOS_RISCO):
        motivos.append("O relato menciona possível risco; confira se a urgência está adequada.")

    ajustada = analise.model_copy(update={"urgencia": urgencia, "confianca": confianca})
    return ajustada, ajustes, motivos


def orgao_para(categoria: Categoria, risco_imediato: bool) -> str:
    orgao = ORGAOS[categoria]
    return f"{orgao} + Defesa Civil (199)" if risco_imediato else orgao
