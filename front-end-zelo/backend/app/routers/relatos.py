"""Endpoints de relatos (visão do cidadão e painel público)."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query, status

from app.core.erros import ErroEntradaInvalida
from app.core.dependencias import limitar_analises, obter_clima, obter_llm, obter_repositorio
from app.pipelines.regras import PRAZOS, orgao_para
from app.pipelines.triagem import analisar_relato
from app.providers.bairros import BAIRROS, listar_bairros
from app.providers.clima import ClimaProvedor
from app.providers.llm import ProvedorLLM
from app.providers.repositorio import Repositorio
from app.schemas.relato import (
    AnaliseResposta,
    Bairro,
    Categoria,
    ConfirmacaoRelato,
    FeedbackEntrada,
    RelatoEntrada,
    RelatoPublico,
    Status,
    Urgencia,
)

router = APIRouter(prefix="/api/v1", tags=["relatos"])


@router.get("/bairros", response_model=list[Bairro])
def bairros():
    return listar_bairros()


@router.post(
    "/relatos/analisar",
    response_model=AnaliseResposta,
    dependencies=[Depends(limitar_analises)],
    summary="Etapa 1: IA analisa o relato (ainda não gera protocolo)",
)
def analisar(
    entrada: RelatoEntrada,
    llm: ProvedorLLM = Depends(obter_llm),
    clima: ClimaProvedor = Depends(obter_clima),
    repo: Repositorio = Depends(obter_repositorio),
):
    if entrada.bairro not in BAIRROS:
        raise ErroEntradaInvalida("Selecione um bairro da lista.")
    return analisar_relato(entrada, llm, clima, repo)


@router.post(
    "/relatos",
    response_model=RelatoPublico,
    status_code=status.HTTP_201_CREATED,
    summary="Etapa 2 (human-in-the-loop): cidadão confirma/corrige e recebe protocolo",
)
def confirmar(confirmacao: ConfirmacaoRelato, repo: Repositorio = Depends(obter_repositorio)):
    entrada, analise, _ = repo.obter_analise(confirmacao.analise_id)
    categoria_ia, urgencia_ia = Categoria(analise["categoria"]), Urgencia(analise["urgencia"])
    corrigida = confirmacao.categoria_final != categoria_ia or confirmacao.urgencia_final != urgencia_ia
    return repo.criar_relato(
        confirmacao.analise_id,
        {
            "criado_em": _agora(),
            "atualizado_em": _agora(),
            "bairro": entrada["bairro"],
            "categoria": confirmacao.categoria_final.value,
            "urgencia": confirmacao.urgencia_final.value,
            "categoria_ia": categoria_ia.value,
            "urgencia_ia": urgencia_ia.value,
            "confianca_ia": analise["confianca"],
            "status": Status.RECEBIDO.value,
            "resumo": analise["resumo"],
            "orgao_responsavel": orgao_para(confirmacao.categoria_final, analise["risco_imediato"]),
            "prazo_estimado_dias": PRAZOS[confirmacao.urgencia_final],
            "descricao_anonimizada": entrada["descricao"],
            "ia_corrigida": int(corrigida),
        },
    )


@router.get("/relatos", response_model=list[RelatoPublico], summary="Painel público (sem texto do cidadão)")
def listar(
    categoria: Categoria | None = None,
    urgencia: Urgencia | None = None,
    bairro: str | None = Query(default=None, max_length=60),
    dias: int | None = Query(default=None, ge=1, le=365),
    incluir_simulados: bool = True,
    repo: Repositorio = Depends(obter_repositorio),
):
    return repo.listar_relatos(
        categoria=categoria.value if categoria else None,
        urgencia=urgencia.value if urgencia else None,
        bairro=bairro,
        dias=dias,
        incluir_simulados=incluir_simulados,
    )


@router.get("/relatos/{protocolo}", response_model=RelatoPublico)
def obter(protocolo: str, repo: Repositorio = Depends(obter_repositorio)):
    return repo.obter_relato(protocolo)


@router.post(
    "/relatos/{protocolo}/feedback",
    response_model=RelatoPublico,
    dependencies=[Depends(limitar_analises)],
    summary="Cidadão avalia a resposta da IA (exige o analise_id do próprio relato)",
)
def feedback(protocolo: str, corpo: FeedbackEntrada, repo: Repositorio = Depends(obter_repositorio)):
    return repo.registrar_feedback(protocolo, corpo.analise_id, corpo.avaliacao, corpo.comentario)


def _agora() -> str:
    return datetime.now(timezone.utc).isoformat()
