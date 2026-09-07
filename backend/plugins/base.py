"""Plugin abstract base class for nosrat WebUI."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class Plugin(ABC):
    """Abstract base class every nosrat plugin must implement.

    Concrete plugins live in their own sub-package::

        plugins/
            gre_ipsec/
                __init__.py
                plugin.py        # contains `GreIpsecPlugin(Plugin)`
                manifest.json
                wizard_schema.json

    The class attributes below are *required* and MUST be set by subclasses
    before any instance is registered. ``manifest`` is loaded from
    ``manifest.json`` by the registry and injected automatically.
    """

    # ── Required class attributes ────────────────────────────────────────
    name: str = ""
    display_name: str = ""
    description: str = ""
    icon: str = ""

    # ── Populated by PluginRegistry from manifest.json ────────────────────
    manifest: dict[str, Any] = {}

    # ── Wizard ────────────────────────────────────────────────────────────

    @abstractmethod
    def get_wizard_schema(self) -> dict[str, Any]:
        """Return a JSON-Schema describing the wizard form fields."""

    # ── Lifecycle ─────────────────────────────────────────────────────────

    @abstractmethod
    async def create(self, params: dict[str, Any]) -> dict[str, Any]:
        """Persist the plugin's configuration. Must NOT start the service."""

    @abstractmethod
    async def start(self, tunnel_id: int) -> dict[str, Any]:
        """Bring the tunnel up. Returns a status dict."""

    @abstractmethod
    async def stop(self, tunnel_id: int) -> dict[str, Any]:
        """Bring the tunnel down. Returns a status dict."""

    @abstractmethod
    async def restart(self, tunnel_id: int) -> dict[str, Any]:
        """Restart the tunnel. Returns a status dict."""

    @abstractmethod
    async def status(self, tunnel_id: int) -> dict[str, Any]:
        """Return the current tunnel status (up/down/error/etc)."""

    @abstractmethod
    async def logs(self, tunnel_id: int, *, lines: int = 100) -> str:
        """Return the most recent log lines for this tunnel."""

    @abstractmethod
    async def destroy(self, tunnel_id: int) -> dict[str, Any]:
        """Remove all configuration and state for this tunnel."""

    # ── Optional helpers ──────────────────────────────────────────────────

    def info(self) -> dict[str, Any]:
        """Return the plugin metadata exposed by ``GET /api/plugins/:id``."""
        return {
            "name": self.name,
            "display_name": self.display_name,
            "description": self.description,
            "icon": self.icon,
            "manifest": self.manifest,
        }