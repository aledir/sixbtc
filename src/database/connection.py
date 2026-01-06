"""
Database Connection Management for SixBTC

Provides database engine, session factory, and initialization utilities.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from contextlib import contextmanager
from typing import Generator

from src.config import load_config
from src.utils import get_logger

logger = get_logger(__name__)

# Global engine and session factory (initialized once)
_engine = None
_SessionFactory = None


def get_engine():
    """
    Get SQLAlchemy engine (singleton)

    Returns:
        SQLAlchemy Engine instance
    """
    global _engine

    if _engine is None:
        config = load_config()

        # Build database URL
        db_user = config.get_required('database.user')
        db_password = config.get_required('database.password')
        db_host = config.get_required('database.host')
        db_port = config.get_required('database.port')
        db_name = config.get_required('database.database')

        db_url = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"

        # Create engine with connection pool - NO defaults (Fast Fail)
        min_conn = config.get_required('database.pool.min_connections')
        max_conn = config.get_required('database.pool.max_connections')
        pool_recycle = config.get_required('database.pool.pool_recycle')

        _engine = create_engine(
            db_url,
            pool_size=min_conn,
            max_overflow=max_conn - min_conn,
            pool_recycle=pool_recycle,
            pool_pre_ping=True,  # Test connections before using
            echo=False  # Set True for SQL query logging
        )

        logger.info(
            f"Database engine created: {db_host}:{db_port}/{db_name} "
            f"(pool: {min_conn}-{max_conn})"
        )

    return _engine


def get_session_factory():
    """
    Get SQLAlchemy session factory (singleton)

    Returns:
        SessionMaker instance
    """
    global _SessionFactory

    if _SessionFactory is None:
        engine = get_engine()
        _SessionFactory = sessionmaker(bind=engine)
        logger.debug("Session factory created")

    return _SessionFactory


@contextmanager
def get_session() -> Generator[Session, None, None]:
    """
    Context manager for database sessions

    Usage:
        >>> with get_session() as session:
        ...     strategies = session.query(Strategy).all()
        ...     # Session auto-committed on success, rolled back on error

    Yields:
        SQLAlchemy Session

    Raises:
        Exception: Re-raises any exceptions after rollback
    """
    SessionFactory = get_session_factory()
    session = SessionFactory()

    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        logger.error(f"Session rollback due to error: {e}", exc_info=True)
        raise
    finally:
        session.close()


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency for database sessions.

    Usage with FastAPI:
        @app.get("/items")
        def get_items(db: Session = Depends(get_db)):
            return db.query(Item).all()

    Note: This is NOT decorated with @contextmanager because
    FastAPI's Depends() handles the generator lifecycle directly.

    Yields:
        SQLAlchemy Session
    """
    SessionFactory = get_session_factory()
    session = SessionFactory()

    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        logger.error(f"Session rollback due to error: {e}", exc_info=True)
        raise
    finally:
        session.close()


def init_db():
    """
    Initialize database

    Creates all tables defined in models.
    Should be called once at application startup.

    Note: For production, use Alembic migrations instead.
    """
    from .models import Base

    engine = get_engine()
    Base.metadata.create_all(engine)
    logger.info("Database tables created/verified")


# Convenience function for testing
if __name__ == "__main__":
    """Test database connection"""
    from rich.console import Console

    console = Console()

    try:
        # Test connection
        engine = get_engine()
        with engine.connect() as conn:
            result = conn.execute("SELECT version()")
            version = result.fetchone()[0]

        console.print(f"[green]✓ Database connection successful[/green]")
        console.print(f"  PostgreSQL version: {version}")

        # Test session
        with get_session() as session:
            result = session.execute("SELECT current_database()")
            db_name = result.fetchone()[0]

        console.print(f"[green]✓ Session management working[/green]")
        console.print(f"  Current database: {db_name}")

    except Exception as e:
        console.print(f"[red]✗ Database connection failed:[/red] {e}")
        raise
