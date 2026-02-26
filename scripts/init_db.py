"""Initialize database with tables and seed data"""
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from core.database import Base, get_db
from core.config import settings
from models import User, Account, Asset


async def init_db():
    """Initialize database tables"""
    engine = create_async_engine(settings.DATABASE_URL)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    print("Database initialized successfully!")


if __name__ == "__main__":
    asyncio.run(init_db())
