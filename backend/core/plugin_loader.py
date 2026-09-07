"""Plugin discovery and lifecycle manager."""
from __future__ import annotations

import importlib
import json
import logging
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from core.config import settings
from plugins.base import Plugin


logger = logging.getLogger("nosrat.plugins")


class PluginLoadError(Exception):
    """Raised when a plugin cannot be loaded."""


class PluginRegistry:
    """In-memory registry of plugin instances keyed by id."""

    def __init__(self) -> None:
        self._plugins: dict[str, Plugin] = {}
        self._manifests: dict[str, dict[str, Any]] = {}
        self._loaded: bool = False

    # ── Discovery / load ────────────────────────────────────────────────

    def load(self, *, only: list[str] | None = None) -> None:
        """Discover and load all enabled plugins."""
        if self._loaded:
            return
        plugins_dir = Path(settings.plugins_dir)
        if not plugins_dir.is_dir():
            logger.warning("plugins directory does not exist: %s", plugins_dir)
            self._loaded = True
            return

        # Make the plugins package importable.
        pkg_root = plugins_dir.parent
        pkg_root_str = str(pkg_root)
        if pkg_root_str not in sys.path:
            sys.path.insert(0, pkg_root_str)

        targets = set(only or settings.enabled_plugins)
        for entry in sorted(plugins_dir.iterdir()):
            if not entry.is_dir():
                continue
            plugin_id = entry.name
            if targets and plugin_id not in targets:
                continue
            try:
                plugin = self._import_plugin(plugin_id)
            except PluginLoadError as exc:
                logger.error("failed to load plugin %s: %s", plugin_id, exc)
                continue
            self._plugins[plugin_id] = plugin
            self._manifests[plugin_id] = plugin.manifest
            logger.info("loaded plugin %s", plugin_id)

        self._loaded = True

    def reload(self) -> None:
        """Drop all plugins and re-discover."""
        self._plugins.clear()
        self._manifests.clear()
        self._loaded = False
        self.load()

    def _import_plugin(self, plugin_id: str) -> Plugin:
        manifest = self._read_manifest(plugin_id)
        module = importlib.import_module(f"plugins.{plugin_id}.plugin")

        cls: type[Plugin] | None = None
        # Prefer a class named after the plugin, otherwise the first Plugin subclass.
        preferred = f"{plugin_id.replace('_', ' ').title().replace(' ', '')}Plugin"
        for candidate_name in (preferred, "Plugin"):
            cand = getattr(module, candidate_name, None)
            if cand is None:
                continue
            if isinstance(cand, type) and issubclass(cand, Plugin) and cand is not Plugin:
                cls = cand
                break

        if cls is None:
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (
                    isinstance(attr, type)
                    and issubclass(attr, Plugin)
                    and attr is not Plugin
                    and attr.__module__ == module.__name__
                ):
                    cls = attr
                    break

        if cls is None:
            raise PluginLoadError(
                f"plugins.{plugin_id}.plugin has no Plugin subclass"
            )

        instance = cls()
        if not isinstance(instance, Plugin):
            raise PluginLoadError(f"{plugin_id} is not a Plugin subclass")
        if instance.name != plugin_id:
            logger.warning(
                "plugin id mismatch: folder=%s name=%s", plugin_id, instance.name
            )
        instance.manifest = manifest
        return instance

    @staticmethod
    def _read_manifest(plugin_id: str) -> dict[str, Any]:
        manifest_path = Path(settings.plugins_dir) / plugin_id / "manifest.json"
        if not manifest_path.is_file():
            raise PluginLoadError(f"missing manifest at {manifest_path}")
        try:
            with manifest_path.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
        except json.JSONDecodeError as exc:
            raise PluginLoadError(f"invalid JSON in {manifest_path}: {exc}") from exc
        if not isinstance(data, dict):
            raise PluginLoadError(
                f"manifest must be an object, got {type(data).__name__}"
            )
        return data

    # ── Queries ──────────────────────────────────────────────────────────

    def __contains__(self, plugin_id: str) -> bool:
        return plugin_id in self._plugins

    def __iter__(self) -> Iterator[Plugin]:
        return iter(self._plugins.values())

    def list(self) -> list[Plugin]:
        return list(self._plugins.values())

    def get(self, plugin_id: str) -> Plugin:
        if plugin_id not in self._plugins:
            raise KeyError(f"plugin not found: {plugin_id}")
        return self._plugins[plugin_id]

    def get_manifest(self, plugin_id: str) -> dict[str, Any]:
        if plugin_id not in self._manifests:
            raise KeyError(f"plugin not found: {plugin_id}")
        return self._manifests[plugin_id]


# Module-level singleton — used as `from core.plugin_loader import plugin_registry`.
plugin_registry = PluginRegistry()