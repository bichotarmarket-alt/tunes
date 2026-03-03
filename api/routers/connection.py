"""
Router para gerenciamento de conexao
"""
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from loguru import logger


router = APIRouter()


class ConnectionHealth(BaseModel):
    """Resposta para verificação de saúde da conexão"""
    status: str
    message: str


@router.get("/health", response_model=ConnectionHealth)
async def connection_health():
    """
    Verifica saúde da conexão
    """
    return ConnectionHealth(
        status="ok",
        message="Conexão ativa"
    )
