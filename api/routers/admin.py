from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from loguru import logger
from datetime import datetime, timedelta
from typing import List, Optional
from pydantic import BaseModel
from pathlib import Path
import re

from core.database import get_db
from models import User
from api.dependencies import get_current_active_user, get_current_superuser
from schemas import UserResponse

router = APIRouter(tags=["admin"])


class UserPlanResponse(BaseModel):
    """Response schema for user plan update"""
    role: str
    vip_start_date: datetime | None
    vip_end_date: datetime | None
    message: str


class DashboardMetrics(BaseModel):
    """Dashboard performance metrics"""
    updated_at: str
    uptime: str
    memory_current: str
    memory_avg: str
    cpu_current: str
    cpu_avg: str
    disk_usage: str
    api_requests: int
    api_success_rate: str
    api_latency_avg: str
    ws_connections: int
    trades_executed: int
    trades_pending: int
    db_queries: int
    db_errors: int
    cache_hit_rate: str
    assets_available: int
    assets_with_data: int


def parse_dashboard_log() -> Optional[DashboardMetrics]:
    """Parse dashboard.log file and extract metrics"""
    try:
        log_path = Path("logs/performance/dashboard.log")
        if not log_path.exists():
            return None
        
        content = log_path.read_text(encoding='utf-8')
        
        # Helper to extract value using regex
        def extract(pattern: str, text: str, default: str = "N/A") -> str:
            match = re.search(pattern, text)
            return match.group(1).strip() if match else default
        
        def extract_int(pattern: str, text: str, default: int = 0) -> int:
            match = re.search(pattern, text)
            return int(match.group(1)) if match else default
        
        # Parse metrics
        updated_at = extract(r"Atualizado:\s+(.+?)\s+UTC", content, "N/A")
        uptime = extract(r"Uptime:\s+(.+)", content, "N/A")
        memory_current = extract(r"Memória Atual:\s+(.+?)\s+", content, "N/A")
        memory_avg = extract(r"Memória Média:\s+(.+?)\s+", content, "N/A")
        cpu_current = extract(r"CPU Atual:\s+(.+?)%", content, "0")
        cpu_avg = extract(r"CPU Média:\s+(.+?)%", content, "0")
        disk_usage = extract(r"Disco Uso:\s+(.+?)%", content, "0")
        
        api_requests = extract_int(r"Total Requisições:\s+(\d+)", content, 0)
        api_success_rate = extract(r"Sucessos:\s+\d+\s+\(([\d.]+)%\)", content, "0%")
        api_latency_avg = extract(r"Latência Média:\s+([\d.]+)\s+ms", content, "0")
        
        ws_connections = extract_int(r"Total Conexões WS:\s+(\d+)", content, 0)
        
        trades_executed = extract_int(r"Trades Executados:\s+(\d+)", content, 0)
        trades_pending = extract_int(r"Trades Pendentes:\s+(\d+)", content, 0)
        
        db_queries = extract_int(r"Queries Executadas:\s+(\d+)", content, 0)
        db_errors = extract_int(r"Erros DB:\s+(\d+)", content, 0)
        
        cache_hit_rate = extract(r"Cache Hit Rate:\s+([\d.]+)%", content, "0%")
        
        assets_available = extract_int(r"Ativos Disponíveis:\s+(\d+)", content, 0)
        assets_with_data = extract_int(r"Ativos com Dados:\s+(\d+)", content, 0)
        
        return DashboardMetrics(
            updated_at=updated_at,
            uptime=uptime,
            memory_current=memory_current,
            memory_avg=memory_avg,
            cpu_current=f"{cpu_current}%",
            cpu_avg=f"{cpu_avg}%",
            disk_usage=f"{disk_usage}%",
            api_requests=api_requests,
            api_success_rate=api_success_rate,
            api_latency_avg=f"{api_latency_avg} ms",
            ws_connections=ws_connections,
            trades_executed=trades_executed,
            trades_pending=trades_pending,
            db_queries=db_queries,
            db_errors=db_errors,
            cache_hit_rate=f"{cache_hit_rate}%",
            assets_available=assets_available,
            assets_with_data=assets_with_data
        )
    except Exception as e:
        logger.error(f"Error parsing dashboard.log: {e}")
        return None


@router.get("/users")
async def list_all_users(
    search: str = Query(None, description="Buscar por nome, email, plano ou telegram username"),
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db)
):
    """Listar todos os usuários (apenas superusuários)"""
    result = await db.execute(select(User))
    users = result.scalars().all()
    
    # Filtrar se houver termo de busca
    if search and search.strip():
        search_lower = search.lower().strip()
        users = [u for u in users if 
            (u.name and search_lower in u.name.lower()) or
            (u.email and search_lower in u.email.lower()) or
            (u.role and search_lower in u.role.lower()) or
            (u.telegram_username and search_lower in u.telegram_username.lower())
        ]
    
    return [
        UserResponse(
            id=user.id,
            email=user.email,
            name=user.name,
            is_active=user.is_active,
            is_superuser=user.is_superuser,
            created_at=user.created_at,
            updated_at=user.updated_at,
            telegram_chat_id=user.telegram_chat_id,
            telegram_username=user.telegram_username,
            role=user.role or 'free',
            vip_start_date=user.vip_start_date,
            vip_end_date=user.vip_end_date
        ) for user in users
    ]


@router.get("/users/search")
async def search_user_by_email(
    email: str = Query(..., description="Email do usuário a buscar"),
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db)
):
    """Buscar usuário por email (apenas superusuários)"""
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=404,
            detail="Usuário não encontrado"
        )
    
    return UserResponse(
        id=user.id,
        email=user.email,
        name=user.name,
        is_active=user.is_active,
        is_superuser=user.is_superuser,
        created_at=user.created_at,
        updated_at=user.updated_at,
        telegram_chat_id=user.telegram_chat_id,
        telegram_username=user.telegram_username,
        role=user.role or 'free',
        vip_start_date=user.vip_start_date,
        vip_end_date=user.vip_end_date
    )


@router.put("/users/{user_id}/plan", response_model=UserPlanResponse)
async def update_user_plan_admin(
    user_id: str,
    role: str = Query(..., description="Plano do usuário: 'free', 'vip', 'vip_plus'"),
    duration_days: int = Query(7, description="Duração em dias para VIP/VIP+"),
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db)
):
    """Atualizar plano do usuário (apenas superusuários)"""
    # Validar role
    valid_roles = ['free', 'vip', 'vip_plus']
    if role not in valid_roles:
        raise HTTPException(
            status_code=400,
            detail=f"Role inválido. Valores válidos: {', '.join(valid_roles)}"
        )
    
    # Buscar usuário
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=404,
            detail="Usuário não encontrado"
        )
    
    # Calcular datas de VIP
    now = datetime.utcnow()
    vip_start_date = None
    vip_end_date = None
    
    if role in ['vip', 'vip_plus']:
        vip_start_date = now
        vip_end_date = now + timedelta(days=duration_days)
    elif role == 'free':
        # Para plano free, remover datas VIP
        vip_start_date = None
        vip_end_date = None
    
    # Atualizar usuário
    user.role = role
    user.vip_start_date = vip_start_date
    user.vip_end_date = vip_end_date
    user.updated_at = now
    
    await db.commit()
    await db.refresh(user)
    
    logger.info(f"✓ [ADMIN] Plano do usuário {user.email} atualizado para {role.upper()}")
    
    return UserPlanResponse(
        role=user.role,
        vip_start_date=user.vip_start_date,
        vip_end_date=user.vip_end_date,
        message=f"Plano atualizado para {role.upper()}"
    )


@router.get("/dashboard", response_model=DashboardMetrics)
async def get_dashboard_metrics(
    current_user: User = Depends(get_current_superuser)
):
    """Obter métricas de performance do dashboard (apenas superusuários)"""
    metrics = parse_dashboard_log()
    
    if not metrics:
        raise HTTPException(
            status_code=503,
            detail="Dashboard metrics not available. Check if dashboard.log exists."
        )
    
    return metrics
