"""Plugin discovery tests."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import create_app
from core.database import init_db
from db.models import User


@pytest.fixture(scope="module")
def client() -> TestClient:
    init_db()
    _ensure_admin()
    app = create_app()
    with TestClient(app) as c:
        yield c


def _ensure_admin() -> None:
    """Guarantee the admin user exists with the password used by these tests."""
    from core.database import session_scope
    from core.security import hash_password

    with session_scope() as db:
        user = db.query(User).filter(User.username == "admin").first()
        if user is None:
            db.add(User(username="admin", password_hash=hash_password("admin"), role="admin", is_active=True))
        else:
            user.password_hash = hash_password("admin")
            user.is_active = True


def _login(client: TestClient) -> str:
    r = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "admin"},
    )
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def test_list_plugins_requires_auth(client: TestClient) -> None:
    r = client.get("/api/plugins")
    assert r.status_code == 401


def test_list_plugins_returns_at_least_gre(client: TestClient) -> None:
    token = _login(client)
    r = client.get("/api/plugins", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200, r.text
    names = [p["name"] for p in r.json()]
    assert "gre_ipsec" in names
    assert "ghost_tunnel" in names


def test_get_plugin_schema(client: TestClient) -> None:
    token = _login(client)
    r = client.get(
        "/api/plugins/gre_ipsec/schema",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["name"] == "gre_ipsec"
    assert "wizard_schema" in body
    assert "step_1" in body["wizard_schema"]


def test_get_unknown_plugin_404(client: TestClient) -> None:
    token = _login(client)
    r = client.get(
        "/api/plugins/does-not-exist",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 404