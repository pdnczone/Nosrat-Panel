"""Application configuration loaded from environment / .env file."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BACKEND_DIR.parent.parent


class Settings(BaseSettings):
    """Runtime configuration for the FastAPI backend."""

    model_config = SettingsConfigDict(
        env_prefix="NOSRAT_",
        env_file=str(BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Server ────────────────────────────────────────────────────────────
    app_name: str = "nosrat WebUI Backend"
    app_version: str = "1.0.0"
    environment: Literal["development", "staging", "production"] = "production"
    host: str = "0.0.0.0"
    port: int = 8080
    workers: int = 1
    reload: bool = False
    debug: bool = False
    cors_origins: list[str] = Field(default_factory=lambda: ["*"])

    # ── Database ──────────────────────────────────────────────────────────
    db_url: str = f"sqlite:///{BACKEND_DIR / 'data' / 'nosrat.db'}"
    db_echo: bool = False

    # ── Security ──────────────────────────────────────────────────────────
    secret_key: str = Field(
        default="CHANGE-ME-IN-PRODUCTION-this-is-only-for-development",
        description="HMAC secret for JWT signing. MUST be overridden in production.",
    )
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 8  # 8 hours
    refresh_token_expire_minutes: int = 60 * 24 * 7  # 7 days
    bcrypt_rounds: int = 12

    # ── Subprocess / CLI ──────────────────────────────────────────────────
    nosrat_bin: str = "/usr/local/bin/nosrat"
    nosrat_cli: str = str(PROJECT_ROOT / "cmd" / "nosrat" / "nosrat.sh")
    command_timeout_sec: int = 30
    long_command_timeout_sec: int = 300

    # ── Crypto / PSK ──────────────────────────────────────────────────────
    psk_dir: str = "/etc/nosrat/secrets"
    psk_file: str = "/etc/nosrat/secrets/psk"
    config_dir: str = "/etc/nosrat"
    config_file: str = "/etc/nosrat/tunnel.yaml"

    # ── Plugins ───────────────────────────────────────────────────────────
    plugins_dir: str = str(BACKEND_DIR / "plugins")
    enabled_plugins: list[str] = Field(default_factory=lambda: ["gre_ipsec", "ghost_tunnel"])

    # ── WebSocket ─────────────────────────────────────────────────────────
    ws_heartbeat_sec: int = 30
    ws_max_connections: int = 100

    # ── Logging ───────────────────────────────────────────────────────────
    log_level: str = "INFO"
    log_file: str = str(BACKEND_DIR / "data" / "backend.log")

    # ── Defaults for the bootstrap admin user ───────────────────────────────────────────────────────
    bootstrap_admin_username: str = "admin"
    bootstrap_admin_password: str = "admin"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()


settings = get_settings()


def ensure_directories() -> None:
    """Make sure data and config directories exist on disk."""
    for path in (
        Path(settings.db_url.replace("sqlite:///", "")).parent,
        Path(settings.log_file).parent,
    ):
        path.mkdir(parents=True, exist_ok=True)