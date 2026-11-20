"""Endpoints da visão do gestor (RBAC por token no cabeçalho X-Gestor-Token)."""

from fastapi import APIRouter, Depends

from app.core.dependencias import exigir_gestor, obter_repositorio
from app.providers.repositorio import Repositorio
from app.schemas.relato import AtualizacaoStatus, RelatoGestor, Status

router = APIRouter(prefix="/api/v1/gestor", tags=["gestor"], dependencies=[Depends(exigir_gestor)])


@router.get("/relatos", response_model=list[RelatoGestor])
def listar(status: Status | None = None, repo: Repositorio = Depends(obter_repositorio)):
    return repo.listar_relatos(status=status.value if status else None)


@router.patch("/relatos/{protocolo}", response_model=RelatoGestor)
def atualizar(protocolo: str, corpo: AtualizacaoStatus, repo: Repositorio = Depends(obter_repositorio)):
    return repo.atualizar_status(protocolo, corpo.status.value, corpo.nota)
