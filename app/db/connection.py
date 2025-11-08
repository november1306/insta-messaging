"""
Database connection management with SQLAlchemy async support.

Supports SQLite (development) and MySQL/PostgreSQL (production) via DATABASE_URL.
"""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import StaticPool
from app.db.models import Base
from app.config import settings
import logging

logger = logging.getLogger(__name__)

# Database engine (will be initialized in init_db)
engine = None
async_session_maker = None


async def init_db():
    """Initialize database connection and create tables."""
    global engine, async_session_maker

    database_url = settings.database_url
    logger.info(f"Initializing database: {database_url.split('://')[0]}")

    # Create async engine with appropriate settings based on database type
    if database_url.startswith("sqlite"):
        # SQLite-specific configuration
        engine = create_async_engine(
            database_url,
            echo=False,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
    else:
        # MySQL/PostgreSQL configuration
        engine = create_async_engine(
            database_url,
            echo=False,
            pool_pre_ping=True,  # Verify connections before using
            pool_recycle=3600,   # Recycle connections after 1 hour
        )
    
    # Create session factory
    async_session_maker = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    
    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    logger.info("✅ Database initialized successfully")


async def get_db_session() -> AsyncSession:
    """
    Get database session for dependency injection.
    
    Usage in FastAPI:
        @app.get("/endpoint")
        async def endpoint(db: AsyncSession = Depends(get_db_session)):
            ...
    
    Note: This session auto-commits on success and auto-rolls back on error.
    Manual commit/rollback in endpoint code is not needed.
    """
    if async_session_maker is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    
    async with async_session_maker() as session:
        try:
            yield session
        except Exception as e:
            await session.rollback()
            logger.error(f"Database session error: {e}")
            raise
        else:
            # Only commit if no exception occurred
            await session.commit()
        finally:
            await session.close()


async def close_db():
    """Close database connection."""
    global engine
    if engine:
        await engine.dispose()
        logger.info("Database connection closed")
