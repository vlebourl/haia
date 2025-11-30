"""Database session management and engine configuration.

This module provides async database session creation, engine configuration,
and FastAPI dependency injection for database access.
"""

import logging
from collections.abc import AsyncGenerator

from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from haia.config import settings

# Logger for SQL query logging
logger = logging.getLogger(__name__)

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


# ============================================================================
# Query Logging Event Hooks
# ============================================================================


@event.listens_for(Engine, "before_cursor_execute")
def log_query_before_execute(
    conn, cursor, statement, parameters, context, executemany
):
    """Log SQL queries before execution (DEBUG level).

    Event hook that logs all SQL statements and their parameters before
    execution. Useful for debugging and monitoring database activity.

    Args:
        conn: Database connection
        cursor: Database cursor
        statement: SQL statement to be executed
        parameters: Parameters for the SQL statement
        context: Execution context
        executemany: Whether this is an executemany operation
    """
    # Log the SQL statement
    logger.debug("SQL Query: %s", statement)

    # Log parameters if present
    if parameters:
        logger.debug("Parameters: %s", parameters)


@event.listens_for(Engine, "after_cursor_execute")
def log_query_after_execute(
    conn, cursor, statement, parameters, context, executemany
):
    """Log query execution completion (DEBUG level).

    Event hook that logs query completion. Can be used to track query
    execution time and results.

    Args:
        conn: Database connection
        cursor: Database cursor
        statement: SQL statement that was executed
        parameters: Parameters used in the SQL statement
        context: Execution context
        executemany: Whether this was an executemany operation
    """
    logger.debug("Query completed: %s rows affected", cursor.rowcount)


# ============================================================================
# Session Management
# ============================================================================


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


# ============================================================================
# Database Initialization
# ============================================================================


async def init_db() -> None:
    """Initialize the database schema.

    Creates all tables defined in Base.metadata if they don't exist.
    This is useful for development and testing environments.

    For production, prefer using Alembic migrations instead.

    Example:
        ```python
        from haia.db import init_db

        # Initialize database on application startup
        @app.on_event("startup")
        async def startup_event():
            await init_db()
        ```

    Raises:
        SQLAlchemyError: If schema creation fails
    """
    from haia.db.models import Base

    logger.info("Initializing database schema...")

    async with engine.begin() as conn:
        # Create all tables
        await conn.run_sync(Base.metadata.create_all)

    logger.info("Database schema initialized successfully")


async def apply_migrations() -> None:
    """Apply pending Alembic migrations automatically.

    Runs 'alembic upgrade head' to apply all pending migrations.
    This is useful for production deployments and CI/CD pipelines.

    Example:
        ```python
        from haia.db import apply_migrations

        # Apply migrations on application startup
        @app.on_event("startup")
        async def startup_event():
            await apply_migrations()
        ```

    Note:
        Requires Alembic to be properly configured with migrations in
        src/haia/db/migrations/ directory.

    Raises:
        subprocess.CalledProcessError: If migration command fails
    """
    import subprocess

    logger.info("Applying pending database migrations...")

    try:
        # Run alembic upgrade head
        result = subprocess.run(
            ["alembic", "upgrade", "head"],
            check=True,
            capture_output=True,
            text=True,
        )

        logger.info("Migrations applied successfully")
        logger.debug(f"Alembic output: {result.stdout}")

    except subprocess.CalledProcessError as e:
        logger.error(f"Migration failed: {e.stderr}")
        raise
    except FileNotFoundError:
        logger.warning("Alembic not found - skipping migrations (install with: pip install alembic)")


async def close_db() -> None:
    """Close database engine and cleanup connections.

    Should be called on application shutdown to ensure all connections
    are properly closed and resources are released.

    Example:
        ```python
        from haia.db import close_db

        # Cleanup on application shutdown
        @app.on_event("shutdown")
        async def shutdown_event():
            await close_db()
        ```
    """
    logger.info("Closing database connections...")
    await engine.dispose()
    logger.info("Database connections closed")
