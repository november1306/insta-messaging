"""
Database connection management with SQLAlchemy async support.

MVP: SQLite only with configurable path.
TODO: Add MySQL/PostgreSQL support in Priority 2 when needed.
"""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy import event
from app.db.models import Base
from app.config import settings
import logging

logger = logging.getLogger(__name__)

# Database engine (will be initialized in init_db)
engine = None
async_session_maker = None


async def init_db():
    """Initialize SQLite database connection and create tables."""
    global engine, async_session_maker

    database_url = settings.database_url
    logger.info(f"Initializing database: {database_url}")

    # Create async engine for SQLite
    engine = create_async_engine(
        database_url,
        echo=False,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    # Enable foreign key enforcement in SQLite
    # Foreign keys are disabled by default in SQLite - this enables CASCADE DELETE
    @event.listens_for(engine.sync_engine, "connect")
    def set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
    
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


def get_db_session_context():
    """
    Get database session for standalone scripts (non-FastAPI context).

    Usage in scripts:
        async with get_db_session_context() as db:
            # Use db session here
            result = await db.execute(select(User))

    This is a proper async context manager, unlike get_db_session which is
    designed for FastAPI dependency injection.
    """
    if async_session_maker is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")

    return async_session_maker()


async def close_db():
    """Close database connection."""
    global engine
    if engine:
        await engine.dispose()
        logger.info("Database connection closed")
