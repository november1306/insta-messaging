"""
Database connection management with SQLAlchemy async support.

YAGNI: SQLite only for now. Add MySQL when deploying to production.
"""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import StaticPool
from app.models.models import Base
import logging

logger = logging.getLogger(__name__)

# Database engine (will be initialized in init_db)
engine = None
async_session_maker = None

# SQLite database file
DATABASE_URL = "sqlite+aiosqlite:///./instagram_automation.db"


async def init_db():
    """Initialize SQLite database connection and create tables."""
    global engine, async_session_maker
    
    logger.info(f"Initializing database: SQLite")
    
    # Create async engine for SQLite
    engine = create_async_engine(
        DATABASE_URL,
        echo=False,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
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
