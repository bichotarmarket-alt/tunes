from fastapi import APIRouter, Depends, HTTPException, Request
from loguru import logger
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi.responses import JSONResponse
from datetime import datetime, timedelta
from pydantic import BaseModel

from services.pocketoption.maintenance_checker import maintenance_checker
from services.pocketoption.maintenance_handler import maintenance_handler
from services.notifications.telegram import telegram_service

router = APIRouter(tags=["maintenance"])
limiter = Limiter(key_func=get_remote_address)


class MaintenanceStatus(BaseModel):
    """Response schema for maintenance status"""
    is_under_maintenance: bool
    last_checked_at: datetime | None


class NotificationResponse(BaseModel):
    """Response schema for notification result"""
    success: bool
    message: str

# Cache simples em memória
_cache = {
    "data": None,
    "expires_at": None
}

def get_cached_status():
    """Retorna status em cache se ainda válido"""
    now = datetime.utcnow()
    if _cache["data"] and _cache["expires_at"] and now < _cache["expires_at"]:
        return _cache["data"]
    return None

def set_cached_status(data):
    """Define status em cache com expiração de 30 segundos"""
    _cache["data"] = data
    _cache["expires_at"] = datetime.utcnow() + timedelta(seconds=30)


@router.get("/status", response_model=MaintenanceStatus)
@limiter.limit("300/minute")  # Rate limiting: 300 requisições por minuto (aumentado para evitar 429)
async def get_maintenance_status(request: Request):
    """Retorna o status de manutenção da PocketOption"""
    # Verificar cache
    cached = get_cached_status()
    if cached:
        return cached

    # Buscar status atual
    data = MaintenanceStatus(
        is_under_maintenance=maintenance_checker.is_under_maintenance,
        last_checked_at=maintenance_checker.last_checked_at
    )

    # Definir cache com expiração de 30 segundos (aumentado para reduzir requisições)
    _cache["data"] = data
    _cache["expires_at"] = datetime.utcnow() + timedelta(seconds=30)

    return data


@router.post("/notify-maintenance-ended", response_model=NotificationResponse)
@limiter.limit("10/minute")  # Rate limiting: 10 requisições por minuto
async def notify_maintenance_ended(request: Request, chat_id: str):
    """Envia notificação no Telegram quando a manutenção terminar"""
    if not telegram_service.enabled:
        return NotificationResponse(
            success=False,
            message="Telegram não está configurado"
        )

    message = """
✅ <b>MANUTENÇÃO TERMINOU!</b>

🎉 A corretora voltou ao normal!
🔄 O sistema está pronto para reiniciar.

⏰ {}
""".format(datetime.utcnow().strftime('%H:%M:%S'))

    success = await telegram_service.send_message(message, chat_id)

    if success:
        return NotificationResponse(
            success=True,
            message="Notificação enviada com sucesso"
        )
    else:
        return NotificationResponse(
            success=False,
            message="Falha ao enviar notificação"
        )
