"""Ponto de entrada da API Zelo (FastAPI).

Rodar localmente (a partir da pasta backend/):
    uvicorn app.main:app --reload
Documentação interativa: http://localhost:8000/docs
"""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import obter_configuracoes
from app.core.erros import registrar_handlers
from app.routers import gestor, relatos, saude

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

cfg = obter_configuracoes()

app = FastAPI(
    title="Zelo API",
    description="Zeladoria urbana com IA — CitizenTech (FIAP Global Solution 2026.2)",
    version="1.0.0",
)

# CORS restritivo: só as origens listadas em ALLOWED_ORIGINS, só os métodos usados.
app.add_middleware(
    CORSMiddleware,
    allow_origins=cfg.origens_permitidas,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH"],
    allow_headers=["Content-Type", "X-Gestor-Token"],
)

registrar_handlers(app)
app.include_router(saude.router)
app.include_router(relatos.router)
app.include_router(gestor.router)
