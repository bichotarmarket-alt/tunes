"""API dependencies"""
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.security import get_current_active_user, get_current_superuser


async def get_db_session() -> AsyncSession:
    """Dependency to get database session"""
    async with get_db() as db:
        yield db


__all__ = ['get_db_session', 'get_current_active_user', 'get_current_superuser']
