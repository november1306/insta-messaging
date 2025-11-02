"""
Database connection management with SQLAlchemy async support.
"""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import StaticPool
from app.models.models import Base
import logging

logger = logging.getLogger(__name__)

# Database engine (will be initialized in init_db)
engine = None
async_session_maker = None


def get_database_url(environment: str = "development") -> str:
    """
    Get database URL based on environment.
    
    For local development: SQLite
    For production: MySQL (from environment variables)
    """
    if environment == "production":
        # MySQL connection for production
        # Will be configured via environment variables during deployment
        from app.config import settings
        return settings.database_url
    else:
        # SQLite for local development
        return "sqlite+aiosqlite:///./instagram_automation.db"


async def init_db(database_url: str = None, environment: str = "development"):
    """
    Initialize database connection and create tables.
    
    Args:
        database_url: Optional database URL override
        environment: Environment name (development/production)
    """
    global engine, async_session_maker
    
    if database_url is None:
        database_url = get_database_url(environment)
    
    logger.info(f"Initializing database: {database_url.split('://')[0]}://...")
    
    # Create async engine
    # For SQLite, we need special configuration
    if database_url.startswith("sqlite"):
        engine = create_async_engine(
            database_url,
            echo=False,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
    else:
        engine = create_async_engine(
            database_url,
            echo=False,
            pool_pre_ping=True,
            pool_size=10,
            max_overflow=20,
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
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def close_db():
    """Close database connection."""
    global engine
    if engine:
        await engine.dispose()
        logger.info("Database connection closed")
