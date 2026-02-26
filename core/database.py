"""Database configuration and session management"""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy.pool import NullPool
from sqlalchemy import event
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from core.config import settings
import os


connect_args = {"check_same_thread": False, "timeout": 60}

# Create async engine for SQLite with NullPool to avoid shared connection issues
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DB_ECHO,
    connect_args=connect_args,
    poolclass=NullPool,  # NullPool = no connection pooling, each request gets its own connection
    pool_pre_ping=True,  # Verify connections before using
)


@event.listens_for(engine.sync_engine, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    # Performance optimizations - only set pragmas that don't require transaction
    cursor.execute("PRAGMA journal_mode=WAL")  # Write-Ahead Logging for better concurrency
    cursor.execute("PRAGMA foreign_keys=ON")  # Enable foreign key constraints
    cursor.execute("PRAGMA busy_timeout=60000")  # Increase timeout to 60 seconds
    cursor.execute("PRAGMA cache_size=-64000")  # 64MB cache (negative = KB)
    cursor.execute("PRAGMA temp_store=MEMORY")  # Store temporary tables in memory
    cursor.execute("PRAGMA mmap_size=268435456")  # 256MB memory-mapped I/O
    cursor.execute("PRAGMA page_size=4096")  # Optimal page size for most systems
    cursor.execute("PRAGMA locking_mode=NORMAL")  # Normal locking mode
    cursor.execute("PRAGMA wal_autocheckpoint=1000")  # Checkpoint every 1000 pages
    # REMOVED: PRAGMA synchronous - cannot be changed inside a transaction
    # The default is usually NORMAL which is sufficient
    cursor.close()

# Create async session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)

# Base class for models
Base = declarative_base()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency for FastAPI to get database session
    
    Usage:
        @router.get("/users")
        async def get_users(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """Initialize database tables"""
    # Create data directory if it doesn't exist
    db_path = settings.DATABASE_URL.replace("sqlite+aiosqlite:///", "")
    db_dir = os.path.dirname(db_path)
    
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)
    
    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db():
    """Close database connections"""
    await engine.dispose()


@asynccontextmanager
async def get_db_context():
    """
    Context manager for database session
    
    Usage:
        async with get_db_context() as db:
            result = await db.execute(query)
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def check_db_connection() -> bool:
    """Check if database connection is working"""
    try:
        async with AsyncSessionLocal() as session:
            await session.execute("SELECT 1")
        return True
    except Exception:
        return False
