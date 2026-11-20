"""Pipeline de triagem: entrada do cidadão -> análise estruturada.

Etapas:
1. Anonimização (LGPD)            -> pipelines/anonimizacao.py
2. Contexto de dados abertos      -> providers/clima.py (Open-Meteo)
3. Classificação pelo LLM         -> providers/llm.py (saída Pydantic)
4. Guarda-corpos determinísticos  -> pipelines/regras.py
5. Registro da análise pendente   -> providers/repositorio.py
   (o relato só vira protocolo depois da confirmação humana)
"""

import time

from app.pipelines.anonimizacao import anonimizar
from app.pipelines.prompts import INSTRUCOES_SISTEMA, VERSAO_PROMPT, montar_conteudo
from app.pipelines.regras import PRAZOS, aplicar_regras, orgao_para
from app.providers.bairros import coordenadas
from app.providers.clima import ClimaProvedor
from app.providers.llm import ProvedorLLM
from app.providers.repositorio import Repositorio
from app.schemas.relato import AnaliseResposta, ContextoClima, RelatoEntrada


def _texto_clima(clima: ContextoClima | None) -> str | None:
    if not clima:
        return None
    prob = f" (probabilidade máxima de {clima.probabilidade_chuva}%)" if clima.probabilidade_chuva is not None else ""
    return f"previsão de {clima.chuva_prevista_mm:.1f} mm de chuva hoje no bairro{prob}."


def analisar_relato(
    entrada: RelatoEntrada,
    llm: ProvedorLLM,
    clima_provedor: ClimaProvedor,
    repo: Repositorio,
) -> AnaliseResposta:
    inicio = time.perf_counter()

    descricao_segura, removidos = anonimizar(entrada.descricao)
    referencia_segura = anonimizar(entrada.referencia)[0] if entrada.referencia else None

    coords = coordenadas(entrada.bairro)
    clima = clima_provedor.previsao_hoje(*coords) if coords else None

    conteudo = montar_conteudo(descricao_segura, entrada.bairro, referencia_segura, _texto_clima(clima))
    analise_ia = llm.analisar(INSTRUCOES_SISTEMA, conteudo)

    analise, ajustes, motivos = aplicar_regras(analise_ia, descricao_segura, clima)

    resposta_parcial = {
        "categoria": analise.categoria,
        "urgencia": analise.urgencia,
        "justificativa_urgencia": analise.justificativa_urgencia,
        "resumo": anonimizar(analise.resumo)[0],
        "orientacoes_cidadao": analise.orientacoes_cidadao[:4],
        "orgao_responsavel": orgao_para(analise.categoria, analise.risco_imediato),
        "prazo_estimado_dias": PRAZOS[analise.urgencia],
        "risco_imediato": analise.risco_imediato,
        "fora_do_escopo": analise.fora_do_escopo,
        "confianca": round(analise.confianca, 2),
        "precisa_revisao_humana": bool(motivos),
        "motivos_revisao": motivos,
        "ajustes_por_regra": ajustes,
        "dados_pessoais_removidos": removidos,
        "contexto_clima": clima,
        "modelo": llm.nome_modelo,
        "versao_prompt": VERSAO_PROMPT,
    }

    entrada_segura = {"descricao": descricao_segura, "bairro": entrada.bairro, "referencia": referencia_segura}
    analise_id = repo.salvar_analise(
        entrada_segura,
        {k: (v.model_dump() if hasattr(v, "model_dump") else getattr(v, "value", v)) for k, v in resposta_parcial.items()},
    )

    latencia_ms = int((time.perf_counter() - inicio) * 1000)
    return AnaliseResposta(analise_id=analise_id, latencia_ms=latencia_ms, **resposta_parcial)
