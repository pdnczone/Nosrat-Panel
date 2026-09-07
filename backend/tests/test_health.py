"""Health endpoint tests."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import create_app
from core.database import init_db


@pytest.fixture(scope="module")
def client() -> TestClient:
    init_db()
    app = create_app()
    with TestClient(app) as c:
        yield c


def test_live_is_public(client: TestClient) -> None:
    r = client.get("/api/health/live")
    assert r.status_code == 200
    body = r.json()
    assert body["overall_ok"] is True
    assert "checks" in body


def test_info_endpoint(client: TestClient) -> None:
    r = client.get("/api/health/info")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "version" in body


def test_deep_check_requires_auth(client: TestClient) -> None:
    r = client.post("/api/health/check")
    assert r.status_code == 401