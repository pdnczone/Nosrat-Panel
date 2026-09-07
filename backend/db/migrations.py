"""Lightweight schema / data migrations.

For now the backend relies on ``Base.metadata.create_all`` for table
creation. This module is the place to put future idempotent data
migrations (e.g. ``seed_default_admin``).
"""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import inspect
from sqlalchemy.orm import Session

from core.config import settings
from core.security import hash_password
from db.models import Setting, User


logger = logging.getLogger("nosrat.migrations")


def _table_exists(db: Session, name: str) -> bool:
    return inspect(db.get_bind()).has_table(name)


def run_migrations() -> None:
    """Apply any pending data migrations."""
    from core.database import session_scope

    with session_scope() as db:
        _seed_admin(db)


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