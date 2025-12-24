"""Database connection and engine management."""

import logging
from typing import Optional

from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine, AsyncConnection
from sqlalchemy.pool import NullPool
from sqlalchemy import text

from app.core.config import settings

logger = logging.getLogger(__name__)

# Global engine instance (singleton)
_engine: Optional[AsyncEngine] = None


def get_db_engine(database_url: Optional[str] = None) -> AsyncEngine:
    """Get or create the database engine singleton.
    
    This function creates a SQLAlchemy async engine configured for PostgreSQL
    using asyncpg. The engine uses connection pooling for production use.
    
    Args:
        database_url: Optional database URL override. If not provided,
                     uses settings.database_url.
    
    Returns:
        AsyncEngine instance configured for async operations.
        
    Raises:
        ValueError: If database_url is not configured in settings and not provided.
    
    Example:
        >>> engine = get_db_engine()
        >>> async with engine.begin() as conn:
        ...     result = await conn.execute(text("SELECT 1"))
    """
    global _engine
    
    if _engine is not None:
        return _engine
    
    # Use provided URL or fall back to settings
    url = database_url or settings.database_url
    
    if not url:
        raise ValueError(
            "Database URL is not configured. Set DATABASE_URL or individual "
            "database settings (DATABASE_HOST, DATABASE_PORT, DATABASE_NAME, "
            "DATABASE_USER, DATABASE_PASSWORD) in environment variables."
        )
    
    logger.info(
        f"Creating database engine - host={settings.database_host}, "
        f"port={settings.database_port}, database={settings.database_name}"
    )
    
    # Create async engine with asyncpg
    # Use default pool settings for production (pool_size=5, max_overflow=10)
    # Set echo=False to avoid logging all SQL (can be enabled for debugging)
    _engine = create_async_engine(
        url,
        echo=False,
        future=True,
        pool_pre_ping=True,  # Verify connections before using them
    )
    
    return _engine


async def test_connection() -> bool:
    """Test database connectivity.
    
    Attempts to connect to the database and execute a simple query.
    Logs detailed error information if connection fails.
    
    Returns:
        True if connection successful, False otherwise.
    
    Example:
        >>> if not await test_connection():
        ...     logger.error("Database is not accessible")
        ...     sys.exit(1)
    """
    try:
        engine = get_db_engine()
        async with engine.connect() as conn:
            # Execute a simple query to verify connectivity
            result = await conn.execute(text("SELECT 1"))
            await result.fetchone()
            
        logger.info("Database connection test successful")
        return True
        
    except Exception as e:
        logger.error(
            f"Database connection test failed: {type(e).__name__}: {str(e)}",
            exc_info=True
        )
        return False


async def close_db_engine() -> None:
    """Close the database engine and dispose of the connection pool.
    
    This should be called during application shutdown to cleanly close
    all database connections.
    
    Example:
        >>> @app.on_event("shutdown")
        ... async def shutdown_event():
        ...     await close_db_engine()
    """
    global _engine
    
    if _engine is not None:
        logger.info("Closing database engine")
        await _engine.dispose()
        _engine = None
