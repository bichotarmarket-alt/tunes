"""Authentication router"""
from fastapi import APIRouter, Depends, HTTPException, status, Body, Request
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import timedelta, datetime
from slowapi import Limiter
from slowapi.util import get_remote_address

from core.database import get_db
from core.security import get_current_active_user
from models import User
from schemas import UserCreate, UserLogin, Token, TokenRefresh, UserResponse, MessageResponse
from pydantic import BaseModel
from services.auth_service import auth_service

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)


class UpdateUserPlan(BaseModel):
    """Schema para atualizar plano do usuário"""
    role: str  # 'free', 'vip', 'vip_plus'
    duration_days: int = 7  # Duração em dias (padrão 7 para VIP semanal, 30 para VIP+ mensal)


class UserPlanResponse(BaseModel):
    """Response schema for user plan update"""
    role: str
    vip_start_date: datetime | None
    vip_end_date: datetime | None
    message: str


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
async def register(user_data: UserCreate, request: Request, db: AsyncSession = Depends(get_db)):
    """Register a new user"""
    try:
        user = await auth_service.register_user(user_data, db)
        return UserResponse(
            id=user.id,
            email=user.email,
            name=user.name,
            is_active=user.is_active,
            is_superuser=user.is_superuser,
            created_at=user.created_at,
            updated_at=user.updated_at
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/login", response_model=Token)
@limiter.limit("5/minute")
async def login(credentials: UserLogin, request: Request, db: AsyncSession = Depends(get_db)):
    """Authenticate user and return tokens"""
    try:
        return await auth_service.authenticate_user(credentials, db)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )


@router.post("/refresh", response_model=Token)
async def refresh_token(token_data: TokenRefresh):
    """Refresh access token"""
    try:
        return await auth_service.refresh_access_token(token_data.refresh_token)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )


@router.post("/logout", response_model=MessageResponse)
async def logout(refresh_token: str = Body(..., embed=True)):
    """Logout user by blacklisting refresh token"""
    await auth_service.logout_user(refresh_token)
    return MessageResponse(message="Logged out successfully")


@router.put("/me/plan", response_model=UserPlanResponse)
async def update_user_plan(
    plan_data: UpdateUserPlan,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Atualizar plano do usuário (Free, VIP, VIP+)"""
    # Validar role
    valid_roles = ['free', 'vip', 'vip_plus']
    if plan_data.role not in valid_roles:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Role inválido. Valores válidos: {', '.join(valid_roles)}"
        )

    # Calcular datas de VIP
    now = datetime.utcnow()
    vip_start_date = None
    vip_end_date = None

    if plan_data.role in ['vip', 'vip_plus']:
        vip_start_date = now
        vip_end_date = now + timedelta(days=plan_data.duration_days)

    # Atualizar usuário
    current_user.role = plan_data.role
    current_user.vip_start_date = vip_start_date
    current_user.vip_end_date = vip_end_date
    current_user.updated_at = now

    await db.commit()
    await db.refresh(current_user)

    return UserPlanResponse(
        role=current_user.role,
        vip_start_date=current_user.vip_start_date,
        vip_end_date=current_user.vip_end_date,
        message=f"Plano atualizado para {plan_data.role.upper()}"
    )
