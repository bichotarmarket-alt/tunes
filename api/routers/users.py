"""Users router"""
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, update
from datetime import datetime, timedelta
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.util import get_remote_address

from core.database import get_db
from core.security import get_current_active_user
from models import User, Trade, Account, Strategy, AutoTradeConfig
from schemas import UserResponse, UserUpdate, UserStats, MessageResponse
from services.notifications.telegram import telegram_service
from api.decorators import cache_response
from pydantic import validator


class TelegramLinkResponse(BaseModel):
    """Response schema for Telegram link"""
    message: str
    telegram_username: str
    telegram_chat_id: int


class LinkTelegramRequest(BaseModel):
    telegram_username: str
    
    @validator('telegram_username')
    def validate_telegram_username(cls, v):
        """Valida formato do username do Telegram"""
        if v:
            # Remove @ se presente
            username = v.lstrip('@')
            # Validar formato: 5-32 caracteres alfanuméricos e underscore
            if not (5 <= len(username) <= 32):
                raise ValueError('Username deve ter entre 5 e 32 caracteres')
            if not username.replace('_', '').isalnum():
                raise ValueError('Username deve conter apenas letras, números e underscore')
        return v


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str
    
    @validator('new_password')
    def validate_password_strength(cls, v):
        """Valida força da senha"""
        if len(v) < 8:
            raise ValueError('A senha deve ter pelo menos 8 caracteres')
        if v == cls.current_password:
            raise ValueError('A nova senha deve ser diferente da senha atual')
        return v


router = APIRouter()
limiter = Limiter(key_func=get_remote_address)


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_active_user)
):
    """Get current user information"""
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        name=current_user.name,
        is_active=current_user.is_active,
        is_superuser=current_user.is_superuser,
        created_at=current_user.created_at,
        updated_at=current_user.updated_at,
        telegram_chat_id=current_user.telegram_chat_id,
        telegram_username=current_user.telegram_username,
        role=current_user.role or 'free',
        vip_start_date=current_user.vip_start_date,
        vip_end_date=current_user.vip_end_date
    )


@router.get("/me/stats", response_model=UserStats)
@cache_response(ttl=300, key_prefix="users:stats")  # Aumentado para 5 min
async def get_user_stats(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get user statistics using SQL aggregation - optimized for 1000+ users"""
    from sqlalchemy import func, case, and_, or_
    
    # Get user's accounts
    result = await db.execute(
        select(Account).where(Account.user_id == current_user.id)
    )
    accounts = result.scalars().all()
    
    # Get account balances
    demo_account = next((acc for acc in accounts if acc.ssid_demo is not None), None)
    demo_balance = demo_account.balance_demo if demo_account else 0.0
    
    real_account = next((acc for acc in accounts if acc.ssid_real is not None), None)
    real_balance = real_account.balance_real if real_account else 0.0
    
    account_ids = [acc.id for acc in accounts]
    
    # SQL aggregation para DEMO trades - tudo em UMA query
    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=7)
    
    # Query otimizada com aggregation para demo
    demo_stats_result = await db.execute(
        select(
            func.count().label('total_trades'),
            func.sum(case((Trade.profit > 0, 1), else_=0)).label('winning_trades'),
            func.sum(case((Trade.profit < 0, 1), else_=0)).label('losing_trades'),
            func.sum(case((Trade.profit.isnot(None), 1), else_=0)).label('trades_with_profit'),
            func.sum(Trade.profit).label('total_profit'),
            func.max(Trade.profit).label('max_profit'),
            func.min(Trade.profit).label('min_profit'),
            func.sum(Trade.duration).label('total_duration'),
            func.sum(case((and_(
                Trade.placed_at >= today_start,
                Trade.profit.isnot(None),
                or_(Trade.status == 'win', Trade.status == 'loss')
            ), Trade.profit), else_=0)).label('lucro_hoje'),
            func.sum(case((and_(
                Trade.placed_at >= week_start,
                Trade.profit.isnot(None),
                or_(Trade.status == 'win', Trade.status == 'loss')
            ), Trade.profit), else_=0)).label('lucro_semana'),
            func.count(case((and_(
                Trade.placed_at >= today_start,
                or_(Trade.status == 'win', Trade.status == 'loss')
            ), 1), else_=None)).label('trades_hoje'),
        )
        .where(
            Trade.account_id.in_(account_ids),
            Trade.connection_type == 'demo',
            or_(Trade.status == 'win', Trade.status == 'loss')  # Apenas finalizados
        )
    )
    demo_stats = demo_stats_result.one()
    
    # Query otimizada com aggregation para REAL trades
    real_stats_result = await db.execute(
        select(
            func.count().label('total_trades'),
            func.sum(case((Trade.profit > 0, 1), else_=0)).label('winning_trades'),
            func.sum(case((Trade.profit < 0, 1), else_=0)).label('losing_trades'),
            func.sum(case((Trade.profit.isnot(None), 1), else_=0)).label('trades_with_profit'),
        )
        .where(
            Trade.account_id.in_(account_ids),
            Trade.connection_type == 'real',
            or_(Trade.status == 'win', Trade.status == 'loss')
        )
    )
    real_stats = real_stats_result.one()
    
    # Calcular estatísticas DEMO
    demo_total = demo_stats.total_trades or 0
    demo_winning = demo_stats.winning_trades or 0
    demo_with_profit = demo_stats.trades_with_profit or 0
    demo_win_rate = (demo_winning / demo_with_profit * 100) if demo_with_profit > 0 else 0
    demo_loss_rate = ((demo_stats.losing_trades or 0) / demo_with_profit * 100) if demo_with_profit > 0 else 0
    
    # Calcular estatísticas REAL
    real_total = real_stats.total_trades or 0
    real_winning = real_stats.winning_trades or 0
    real_with_profit = real_stats.trades_with_profit or 0
    real_win_rate = (real_winning / real_with_profit * 100) if real_with_profit > 0 else 0
    real_loss_rate = ((real_stats.losing_trades or 0) / real_with_profit * 100) if real_with_profit > 0 else 0
    
    # Melhor estratégia (aggregation em SQL)
    melhor_estrategia = "N/A"
    melhor_win_rate = 0
    
    strategy_stats_result = await db.execute(
        select(
            Trade.strategy_id,
            func.count().label('total'),
            func.sum(case((Trade.profit > 0, 1), else_=0)).label('wins')
        )
        .where(
            Trade.account_id.in_(account_ids),
            Trade.strategy_id.isnot(None),
            or_(Trade.status == 'win', Trade.status == 'loss')
        )
        .group_by(Trade.strategy_id)
    )
    
    strategy_stats = strategy_stats_result.all()
    best_strategy_id = None
    
    for row in strategy_stats:
        if row.total > 0:
            win_rate = (row.wins / row.total * 100)
            if win_rate > melhor_win_rate:
                melhor_win_rate = win_rate
                best_strategy_id = row.strategy_id
    
    if best_strategy_id:
        strategy_name_result = await db.execute(
            select(Strategy.name).where(Strategy.id == best_strategy_id)
        )
        strategy_name = strategy_name_result.scalar()
        if strategy_name:
            melhor_estrategia = strategy_name
    
    # Calcular tempo ativo
    total_seconds = demo_stats.total_duration or 0
    hours = int(total_seconds // 3600)
    minutes = int((total_seconds % 3600) // 60)
    tempo_ativo = f"{hours}h {minutes}m"
    
    # Taxa de sucesso geral
    total_completed = demo_total + real_total
    total_completed_winning = demo_winning + real_winning
    taxa_sucesso = (total_completed_winning / (demo_with_profit + real_with_profit) * 100) if (demo_with_profit + real_with_profit) > 0 else 0.0
    
    # Highest balance
    highest_balance = None
    if account_ids:
        autotrade_result = await db.execute(
            select(AutoTradeConfig.highest_balance)
            .where(AutoTradeConfig.account_id.in_(account_ids))
            .where(AutoTradeConfig.highest_balance.isnot(None))
            .order_by(AutoTradeConfig.highest_balance.desc())
        )
        highest_balance_row = autotrade_result.first()
        if highest_balance_row:
            highest_balance = highest_balance_row[0]
    
    return UserStats(
        balance_demo=demo_balance,
        balance_real=real_balance,
        win_rate_demo=demo_win_rate,
        win_rate_real=real_win_rate,
        loss_rate_demo=demo_loss_rate,
        loss_rate_real=real_loss_rate,
        total_trades_demo=demo_total,
        total_trades_real=real_total,
        # Campos adicionais
        lucro_hoje=demo_stats.lucro_hoje or 0.0,
        lucro_semana=demo_stats.lucro_semana or 0.0,
        melhor_estrategia=melhor_estrategia,
        taxa_sucesso=taxa_sucesso,
        trades_hoje=demo_stats.trades_hoje or 0,
        maior_ganho=demo_stats.max_profit or 0.0,
        maior_perda=demo_stats.min_profit or 0.0,
        tempo_ativo=tempo_ativo,
        highest_balance=highest_balance,
    )


@router.put("/me", response_model=UserResponse)
async def update_current_user(
    user_update: UserUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Update current user information"""
    # Update fields if provided
    if user_update.name is not None:
        current_user.name = user_update.name
    
    if user_update.email is not None:
        # Check if email already exists
        result = await db.execute(
            select(User).where(
                User.email == user_update.email,
                User.id != current_user.id
            )
        )
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
        current_user.email = user_update.email

    current_user.updated_at = datetime.utcnow()
    
    await db.commit()
    await db.refresh(current_user)

    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        name=current_user.name,
        is_active=current_user.is_active,
        is_superuser=current_user.is_superuser,
        created_at=current_user.created_at,
        updated_at=current_user.updated_at,
        telegram_chat_id=current_user.telegram_chat_id,
        telegram_username=current_user.telegram_username,
        role=current_user.role or 'free',
        vip_start_date=current_user.vip_start_date,
        vip_end_date=current_user.vip_end_date
    )


@router.post("/me/link-telegram", response_model=TelegramLinkResponse)
@limiter.limit("3/minute")
async def link_telegram(
    request: Request,
    link_request: LinkTelegramRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Vincular Telegram à conta do usuário usando username"""
    # Capturar Chat IDs de usuários que enviaram mensagens para o bot
    await telegram_service.capture_chat_id_from_message()
    
    # Buscar Chat ID do Telegram a partir do username
    normalized_username = link_request.telegram_username.lstrip('@')
    chat_id = await telegram_service.get_chat_id_from_username(normalized_username)
    
    if not chat_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username não encontrado ou usuário não iniciou conversa com o bot. Por favor, envie uma mensagem para @tunestrade_bot antes de vincular."
        )
    
    # Impedir duplicidade de chat_id/username entre usuários
    existing_user_result = await db.execute(
        select(User).where(
            User.id != current_user.id,
            ((User.telegram_chat_id == chat_id) | (User.telegram_username == normalized_username))
        )
    )
    existing_user = existing_user_result.scalar_one_or_none()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Este Telegram já está vinculado a outra conta. Desvincule antes de continuar."
        )

    # Salvar telegram_chat_id e telegram_username
    current_user.telegram_chat_id = chat_id
    current_user.telegram_username = normalized_username
    current_user.updated_at = datetime.utcnow()
    
    await db.commit()
    await db.refresh(current_user)
    
    return TelegramLinkResponse(
        message="Telegram vinculado com sucesso",
        telegram_username=current_user.telegram_username,
        telegram_chat_id=chat_id
    )


@router.post("/me/change-password", response_model=MessageResponse)
@limiter.limit("5/minute")
async def change_password(
    request: Request,
    change_request: ChangePasswordRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Alterar senha do usuário"""
    from core.security import verify_password, get_password_hash
    
    # Verificar senha atual
    if not verify_password(change_request.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Senha atual incorreta"
        )
    
    # Verificar se a nova senha é diferente da atual
    if verify_password(change_request.new_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A nova senha deve ser diferente da senha atual"
        )
    
    # Atualizar senha
    current_user.hashed_password = get_password_hash(change_request.new_password)
    current_user.updated_at = datetime.utcnow()
    
    await db.commit()
    await db.refresh(current_user)
    
    return MessageResponse(message="Senha alterada com sucesso")


@router.delete("/me/unlink-telegram", response_model=MessageResponse)
async def unlink_telegram(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Desvincular Telegram da conta do usuário"""
    current_user.telegram_chat_id = None
    current_user.telegram_username = None
    current_user.updated_at = datetime.utcnow()
    
    await db.commit()
    await db.refresh(current_user)
    
    return MessageResponse(message="Telegram desvinculado com sucesso")
