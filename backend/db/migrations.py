"""Lightweight schema / data migrations.

For now the backend relies on ``Base.metadata.create_all`` for table
creation. This module is the place to put future idempotent data
migrations (e.g. ``seed_default_admin``).
"""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from core.config import settings
from core.security import hash_password
from db.models import NodeInstallJob, Server, Setting, User


logger = logging.getLogger("nosrat.migrations")


def _table_exists(db: Session, name: str) -> bool:
    return inspect(db.get_bind()).has_table(name)


def _column_exists(db: Session, table: str, column: str) -> bool:
    cols = inspect(db.get_bind()).get_columns(table)
    return any(c["name"] == column for c in cols)


def run_migrations() -> None:
    """Apply any pending data migrations."""
    from core.database import session_scope

    with session_scope() as db:
        _seed_admin(db)
        _backfill_node_defaults(db)
        _seed_settings(db)


def _seed_admin(db: Session) -> None:
    """Create the bootstrap admin user if it doesn't already exist."""
    if not _table_exists(db, "users"):
        return

    existing = (
        db.query(User).filter(User.username == settings.bootstrap_admin_username).first()
    )
    if existing is not None:
        return

    admin = User(
        username=settings.bootstrap_admin_username,
        password_hash=hash_password(settings.bootstrap_admin_password),
        role="admin",
        is_active=True,
    )
    db.add(admin)
    db.commit()
    logger.info(
        "bootstrapped admin user '%s' (change the password immediately)",
        settings.bootstrap_admin_username,
    )


def _backfill_node_defaults(db: Session) -> None:
    """Backfill defaults for legacy ``servers`` rows after a schema upgrade.

    The new ``Server`` columns (``node_*``) are added by ``create_all`` but
    existing rows have ``NULL`` for the strings.  Idempotent – safe to run
    on every boot.
    """
    if not _table_exists(db, "servers"):
        return
    try:
        # Make sure every existing server has at least an empty node token
        # and the default node_status so the API never returns NULL.
        db.execute(
            text(
                "UPDATE servers SET node_status = COALESCE(node_status, 'offline') "
                "WHERE node_status IS NULL OR node_status = ''"
            )
        )
        db.execute(
            text(
                "UPDATE servers SET node_installed = COALESCE(node_installed, 0) "
                "WHERE node_installed IS NULL"
            )
        )
        db.commit()
    except Exception as exc:  # noqa: BLE001
        logger.warning("node backfill skipped: %s", exc)
        db.rollback()


def _seed_settings(db: Session) -> None:
    """Seed default KV settings (placeholder for future use)."""
    defaults: dict[str, Any] = {
        "language": "en",
        "theme": "dark",
        "auto_refresh_seconds": 5,
    }
    for key, value in defaults.items():
        if db.get(Setting, key) is None:
            db.add(Setting(key=key, value=value))
    db.commit()


# Public re-export so other modules can introspect schema state without
# duplicating helpers.
__all__ = [
    "run_migrations",
    "NodeInstallJob",  # noqa: F401 – keep class discoverable for tooling
]