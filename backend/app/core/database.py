import logging
from typing import Generator, Optional
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session, DeclarativeBase
from app.core.config import settings

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    """Base declarative class for all SQLAlchemy 2.x models."""
    pass


# Initialize SQLAlchemy Engine with connection pool suited for Supabase Session Pooler
engine: Optional[Engine] = None
SessionLocal: Optional[sessionmaker[Session]] = None

db_url = settings.sync_database_url
if db_url:
    try:
        engine = create_engine(
            db_url,
            pool_pre_ping=True,
            pool_size=10,
            max_overflow=20,
            pool_recycle=300,
            echo=False,
        )
        SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=engine,
        )
        logger.info("Database engine initialized with pooler settings.")
    except Exception as e:
        logger.error("Failed to initialize database engine: %s", type(e).__name__)
        engine = None
        SessionLocal = None
else:
    logger.warning("DATABASE_URL is not configured. Database sessions will be unavailable.")


def get_db() -> Generator[Optional[Session], None, None]:
    """
    FastAPI dependency yielding a database session with managed lifecycle.
    Automatically rolls back uncommitted changes if an exception occurs
    and ensures the session is closed.
    """
    if SessionLocal is None:
        yield None
        return

    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def check_database_health() -> str:
    """
    Safely checks database connectivity without exposing connection details.
    Returns: 'connected', 'disconnected', or 'not_configured'
    """
    if not settings.DATABASE_URL or not settings.DATABASE_URL.strip():
        return "not_configured"

    if engine is None:
        return "disconnected"

    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return "connected"
    except Exception as e:
        logger.warning("Database health check ping failed: %s", type(e).__name__)
        return "disconnected"
