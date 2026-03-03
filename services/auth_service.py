"""Authentication service layer"""
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime

from models import User, Account
from schemas import UserCreate, UserLogin, Token
from core.security import (
    verify_password,
    get_password_hash,
    create_access_token,
    create_refresh_token,
    maybe_upgrade_password_hash
)
from core.security.refresh_blacklist import refresh_token_blacklist
from loguru import logger


class AuthService:
    """Service layer for authentication operations"""
    
    @staticmethod
    async def register_user(
        user_data: UserCreate,
        db: AsyncSession
    ) -> User:
        """Register a new user"""
        # Check if email already exists
        result = await db.execute(select(User).where(User.email == user_data.email))
        if result.scalar_one_or_none():
            raise ValueError("Email already registered")

        # Create new user
        hashed_password = get_password_hash(user_data.password)
        user = User(
            email=user_data.email,
            hashed_password=hashed_password,
            name=user_data.name
        )
        
        db.add(user)
        await db.commit()
        await db.refresh(user)

        # Create default trading account
        account = Account(
            user_id=user.id,
            name=f"Conta de {user_data.name}",
            autotrade_demo=True,
            autotrade_real=False,
            uid=0,
            platform=0,
            is_active=True,
        )
        db.add(account)
        await db.commit()
        
        logger.info(f"User registered: {user.email}")
        return user
    
    @staticmethod
    async def authenticate_user(
        credentials: UserLogin,
        db: AsyncSession
    ) -> Token:
        """Authenticate user and return tokens"""
        # Get user
        result = await db.execute(
            select(User).where(User.email == credentials.email)
        )
        user = result.scalar_one_or_none()

        if not user or not verify_password(credentials.password, user.hashed_password):
            raise ValueError("Incorrect email or password")

        # Upgrade password hash if needed
        await maybe_upgrade_password_hash(user, credentials.password, db)

        if not user.is_active:
            raise ValueError("Inactive user")

        # Create tokens
        access_token = create_access_token(data={"sub": user.email})
        refresh_token = create_refresh_token(data={"sub": user.email})

        logger.info(f"User authenticated: {user.email}")
        return Token(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=30 * 60  # 30 minutes
        )
    
    @staticmethod
    async def refresh_access_token(
        refresh_token: str
    ) -> Token:
        """Refresh access token"""
        # Check if refresh token is blacklisted
        if await refresh_token_blacklist.is_blacklisted(refresh_token):
            raise ValueError("Refresh token has been revoked")
        
        # Decode token
        from core.security import decode_token
        payload = decode_token(refresh_token)
        
        if payload is None:
            raise ValueError("Invalid refresh token")

        email = payload.get("sub")
        if not email:
            raise ValueError("Invalid refresh token")

        # Create new access token
        access_token = create_access_token(data={"sub": email})

        return Token(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=30 * 60
        )
    
    @staticmethod
    async def logout_user(refresh_token: str) -> None:
        """Logout user by blacklisting refresh token"""
        await refresh_token_blacklist.add(refresh_token)
        logger.info("User logged out")


auth_service = AuthService()
