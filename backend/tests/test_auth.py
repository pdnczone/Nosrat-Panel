"""Authentication tests."""
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
    app = create_app()
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module", autouse=True)
def _ensure_admin_user() -> None:
    """Make sure the bootstrap admin exists with a known password."""
    from core.database import session_scope

    init_db()
    run_migrations()
    with session_scope() as db:
        user = db.query(User).filter(User.username == app_settings.bootstrap_admin_username).first()
        if user is None:
            user = User(
                username=app_settings.bootstrap_admin_username,
                role="admin",
                is_active=True,
            )
            db.add(user)
        # Always reset password so tests can log in with known creds
        user.password_hash = hash_password("test-pass-123")
        db.commit()


def test_login_bad_credentials(client: TestClient) -> None:
    r = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "wrong"},
    )
    assert r.status_code == 401


def test_login_success_and_me(client: TestClient) -> None:
    r = client.post(
        "/api/auth/login",
        json={"username": app_settings.bootstrap_admin_username, "password": "test-pass-123"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["token_type"] == "bearer"
    token = body["access_token"]
    assert token

    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["username"] == app_settings.bootstrap_admin_username


def test_protected_without_token(client: TestClient) -> None:
    r = client.get("/api/auth/me")
    assert r.status_code == 401


def test_logout(client: TestClient) -> None:
    r = client.post(
        "/api/auth/login",
        json={"username": app_settings.bootstrap_admin_username, "password": "test-pass-123"},
    )
    token = r.json()["access_token"]
    out = client.post(
        "/api/auth/logout",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert out.status_code == 200