"""
Router para gerenciamento de conexão (ngrok, Google Sheets)
"""
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from services.ngrok_manager import NgrokManager
from loguru import logger


router = APIRouter()


class NgrokUrlResponse(BaseModel):
    """Resposta com URL do ngrok"""
    url: str | None
    message: str


class NgrokUpdateResponse(BaseModel):
    """Resposta para atualização de URL do ngrok"""
    message: str
    url: str | None


class ConnectionHealth(BaseModel):
    """Resposta para verificação de saúde da conexão"""
    google_sheets_connected: bool
    ngrok_running: bool
    ngrok_url: str | None
    google_sheets_url: str | None


@router.get("/ngrok-url", response_model=NgrokUrlResponse)
async def get_ngrok_url():
    """
    Retorna URL atual do ngrok capturado do Google Sheets
    """
    try:
        sheet_id = "1Jd2Hyriq_L5g7G4jaT4bFIvkwi56JoBXuScM-BOoIbo"
        manager = NgrokManager(sheet_id)
        
        url = manager.get_url_from_google_sheets()
        
        if url:
            return NgrokUrlResponse(
                url=url,
                message="URL do ngrok obtido com sucesso"
            )
        else:
            return NgrokUrlResponse(
                url=None,
                message="Nenhum URL do ngrok encontrado no Google Sheets"
            )
    
    except Exception as e:
        logger.error(f"Erro ao obter URL do ngrok: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao obter URL do ngrok: {str(e)}"
        )


@router.post("/update-ngrok-url", response_model=NgrokUpdateResponse)
async def update_ngrok_url():
    """
    Força atualização do URL do ngrok no Google Sheets
    """
    try:
        sheet_id = "1Jd2Hyriq_L5g7G4jaT4bFIvkwi56JoBXuScM-BOoIbo"
        manager = NgrokManager(sheet_id)
        
        success = manager.update_and_save()
        
        if success:
            return NgrokUpdateResponse(
                message="URL do ngrok atualizado com sucesso",
                url=manager.ngrok_url
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Falha ao atualizar URL do ngrok"
            )
    
    except Exception as e:
        logger.error(f"Erro ao atualizar URL do ngrok: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao atualizar URL do ngrok: {str(e)}"
        )


@router.get("/health", response_model=ConnectionHealth)
async def connection_health():
    """
    Verifica saúde da conexão ngrok
    """
    try:
        sheet_id = "1Jd2Hyriq_L5g7G4jaT4bFIvkwi56JoBXuScM-BOoIbo"
        manager = NgrokManager(sheet_id)
        
        url = manager.get_url_from_google_sheets()
        ngrok_url = manager.get_ngrok_url()
        
        return ConnectionHealth(
            google_sheets_connected=url is not None,
            ngrok_running=ngrok_url is not None,
            ngrok_url=ngrok_url,
            google_sheets_url=url
        )
    
    except Exception as e:
        logger.error(f"Erro ao verificar saúde da conexão: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao verificar saúde: {str(e)}"
        )
