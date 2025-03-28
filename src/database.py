import logging
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlmodel import SQLModel

from src.config import settings


logger = logging.getLogger(__name__)


engine = create_async_engine(
    str(settings.DATABASE_URL),
    echo=False,
    future=True,
    pool_size=20,
    max_overflow=40,
    pool_timeout=60,
    pool_recycle=300,
    pool_pre_ping=True,
)
async_session = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
    class_=AsyncSession,
)


async def init_db() -> None:
    """Initialize database."""
    async with engine.begin() as conn:
        # Create all tables if they don't exist
        await conn.run_sync(SQLModel.metadata.create_all)
    logger.info("Database initialized")


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Get async database session."""
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()
