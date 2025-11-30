"""Database session management and engine configuration.

This module provides async database session creation, engine configuration,
and FastAPI dependency injection for database access.
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from haia.config import settings

# Create async engine
engine: AsyncEngine = create_async_engine(
    settings.database_url,
    echo=False,  # Set to True for SQL logging during development
    pool_size=5,
    max_overflow=10,
)

# Create session factory
async_session = async_sessionmaker(
    engine,
    expire_on_commit=False,  # Keep objects usable after commit
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for database sessions.

    Provides async session with automatic commit/rollback handling.
    Use with FastAPI's Depends() for dependency injection.

    Example:
        @app.post("/api/endpoint")
        async def endpoint(db: AsyncSession = Depends(get_db)):
            # Use db session here
            pass

    Yields:
        AsyncSession: Database session for the request lifecycle
    """
    async with async_session() as session:
        try:
            yield session
            await session.commit()  # Auto-commit on success
        except Exception:
            await session.rollback()  # Rollback on error
            raise
        finally:
            await session.close()
