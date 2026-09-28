"""SQLAlchemy engine, session factory, declarative Base and the get_db dependency.

Supports both MySQL (production, via DATABASE_URL) and SQLite (automated tests).
"""
import logging
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    """Declarative base shared by every Phase 1 model."""


def _build_engine():
    url = settings.DATABASE_URL
    if url.startswith("sqlite"):
        # StaticPool + shared connection keeps :memory: databases alive across
        # sessions, which is exactly what the test suite needs.
        return create_engine(
            url,
            connect_args={"check_same_thread": False},
            poolclass=__import__("sqlalchemy").pool.StaticPool,
            echo=False,
        )
    return create_engine(
        url,
        pool_pre_ping=True,   # re-validate stale MySQL connections
        pool_recycle=3600,    # avoid MySQL's 8h wait_timeout drops
        echo=False,
    )


engine = _build_engine()

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency yielding a database session (commit on success)."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
