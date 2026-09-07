"""SQLAlchemy engine, session factory and base class."""
from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from typing import Any

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from core.config import ensure_directories, settings


class Base(DeclarativeBase):
    """Declarative base class for all ORM models."""

    type_annotation_map: dict[type, Any] = {}


def _make_engine(url: str, echo: bool) -> Engine:
    connect_args: dict[str, Any] = {}
    if url.startswith("sqlite"):
        connect_args["check_same_thread"] = False

    engine = create_engine(
        url,
        echo=echo,
        connect_args=connect_args,
        future=True,
        pool_pre_ping=True,
    )

    if url.startswith("sqlite"):
        @event.listens_for(engine, "connect")
        def _enable_fk(dbapi_conn: Any, _conn_record: Any) -> None:  # noqa: ANN001
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA foreign_keys=ON")
            cur.execute("PRAGMA journal_mode=WAL")
            cur.close()

    return engine


ensure_directories()
engine: Engine = _make_engine(settings.db_url, settings.db_echo)
SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
    future=True,
)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def session_scope() -> Generator[Session, None, None]:
    """Context manager for use outside the FastAPI request lifecycle."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def init_db() -> None:
    """Create all tables. Import models first so they are registered."""
    # Imported here to avoid circular imports.
    from db import models  # noqa: F401

    Base.metadata.create_all(bind=engine)