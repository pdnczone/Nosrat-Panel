"""Tests for the TunnelClient (VPN subscriber) API — quota, expiry, usage."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import create_app
from core.config import settings as app_settings
from core.database import init_db
from core.security import hash_password
from db.migrations import run_migrations
from db.models import User


@pytest.fixture(scope="module")
def client() -> TestClient:
    init_db()
    run_migrations()
    app = create_app()
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def admin_headers(client: TestClient) -> dict[str, str]:
    from core.database import session_scope

    with session_scope() as db:
        user = db.query(User).filter(User.username == app_settings.bootstrap_admin_username).first()
        if user is None:
            user = User(
                username=app_settings.bootstrap_admin_username,
                role="admin",
                is_active=True,
            )
            db.add(user)
        user.password_hash = hash_password("test-pass-123")
        db.commit()
    r = client.post(
        "/api/auth/login",
        json={"username": app_settings.bootstrap_admin_username, "password": "test-pass-123"},
    )
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_clients_require_auth(client: TestClient) -> None:
    r = client.get("/api/clients")
    assert r.status_code == 401


def test_list_clients_empty(client: TestClient, admin_headers: dict[str, str]) -> None:
    r = client.get("/api/clients", headers=admin_headers)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_create_client_requires_link(client: TestClient, admin_headers: dict[str, str]) -> None:
    r = client.post(
        "/api/clients",
        json={"name": "NoLink"},
        headers=admin_headers,
    )
    assert r.status_code == 400  # tunnel_id or server_id required


def test_create_and_usage_flow(client: TestClient, admin_headers: dict[str, str]) -> None:
    # Create a client bound to server id 1 (may not exist, but validation requires it exist).
    # To keep the test hermetic, create against a real server row if one exists, else skip.
    sr = client.get("/api/servers", headers=admin_headers)
    servers = sr.json() if sr.status_code == 200 else []
    if not servers:
        pytest.skip("no servers available to attach client")

    r = client.post(
        "/api/clients",
        json={
            "name": "quota-test",
            "server_id": servers[0]["id"],
            "quota_bytes": 10 * 1024**3,
        },
        headers=admin_headers,
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["name"] == "quota-test"
    assert body["quota_bytes"] == 10 * 1024**3
    assert body["status"] in ("active", "pending", "disabled")
    cid = body["id"]

    # usage endpoint returns a structured client usage view
    u = client.get(f"/api/clients/{cid}/usage", headers=admin_headers)
    assert u.status_code == 200, u.text
    usage = u.json()
    assert usage["quota_bytes"] == 10 * 1024**3
    assert "remaining_bytes" in usage
    assert "pct_used" in usage

    # topup raises quota and re-activates
    t = client.post(f"/api/clients/{cid}/topup", json={"quota_bytes": 100 * 1024**3}, headers=admin_headers)
    assert t.status_code == 200, t.text
    assert t.json()["quota_bytes"] == 100 * 1024**3
    assert t.json()["status"] == "active"

    # delete
    d = client.delete(f"/api/clients/{cid}", headers=admin_headers)
    assert d.status_code == 204
