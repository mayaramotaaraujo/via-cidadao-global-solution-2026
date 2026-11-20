from fastapi import APIRouter, Depends

from app.core.config import Configuracoes, obter_configuracoes

router = APIRouter(tags=["saúde"])


@router.get("/health")
def health(cfg: Configuracoes = Depends(obter_configuracoes)):
    # Não expõe a chave nem detalhes sensíveis: só se a IA está configurada.
    return {
        "status": "ok",
        "ia_configurada": cfg.llm_provider == "fake" or cfg.openai_api_key is not None,
        "provedor": cfg.llm_provider,
    }
