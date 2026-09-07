"""Shared pytest fixtures."""
from __future__ import annotations

import os
import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def temp_dir() -> Iterator[Path]:
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)


@pytest.fixture(autouse=True, scope="session")
def _isolated_env(temp_dir: Path) -> Iterator[None]:
    db = temp_dir / "test.db"
    log = temp_dir / "test.log"
    env = {
        "NOSRAT_ENVIRONMENT": "test",
        "NOSRAT_DB_URL": f"sqlite:///{db}",
        "NOSRAT_LOG_FILE": str(log),
        "NOSRAT_SECRET_KEY": "test-secret-key-for-tests-only",
        "NOSRAT_DEBUG": "false",
    }
    old = {k: os.environ.get(k) for k in env}
    os.environ.update(env)
    try:
        yield
    finally:
        for k, v in old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v