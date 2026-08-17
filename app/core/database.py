from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import (AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine)
from app.core.config import settings

# 1. Async Engine Setup with connecton pooling 
engine: AsyncEngine = create_async_engine(
    settings.SQLALCHEMY_DATABASE_URI,
    echo=(settings.ENVIRONMENT == "development"), # Log SQL Queries in dev mode
    future = True,
    pool_pre_ping = True, # test connection validity before using from pool
    pool_size = settings.DB_POOL_SIZE,
    max_overflow = settings.DB_MAX_OVERFLOW,
    pool_timeout = settings.DB_POOL_TIMEOUT,
    pool_recycle = settings.DB_POOL_RECYCLE,
)

# 2. Async Session factory
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False, #Prevent atrributes from expiring after commit
)

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Yields an active database session for a single request lifecycle,
    automatically rolling back in case of exceptions and closing the session.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


