"""Plugin discovery + introspection endpoints."""
from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from core.deps import get_current_user
from core.plugin_loader import plugin_registry
from db.models import User


router = APIRouter(prefix="/api/plugins", tags=["plugins"])


# ── Schemas ────────────────────────────────────────────────────────────────


class PluginOut(BaseModel):
    name: str
    display_name: str
    description: str
    icon: str
    manifest: dict[str, Any]


class WizardSchemaResponse(BaseModel):
    name: str
    wizard_schema: dict[str, Any]


# ── Routes ─────────────────────────────────────────────────────────────────


@router.get("", response_model=list[PluginOut])
async def list_plugins(
    _user: Annotated[User, Depends(get_current_user)],
) -> list[PluginOut]:
    plugin_registry.load()
    return [PluginOut(**p.info()) for p in plugin_registry.list()]


@router.get("/{plugin_id}", response_model=PluginOut)
async def get_plugin(
    plugin_id: str,
    _user: Annotated[User, Depends(get_current_user)],
) -> PluginOut:
    plugin_registry.load()
    try:
        plugin = plugin_registry.get(plugin_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"plugin not found: {plugin_id}",
        ) from exc
    return PluginOut(**plugin.info())


@router.get("/{plugin_id}/schema", response_model=WizardSchemaResponse)
async def get_plugin_schema(
    plugin_id: str,
    _user: Annotated[User, Depends(get_current_user)],
) -> WizardSchemaResponse:
    plugin_registry.load()
    try:
        plugin = plugin_registry.get(plugin_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"plugin not found: {plugin_id}",
        ) from exc
    return WizardSchemaResponse(
        name=plugin.name, wizard_schema=plugin.get_wizard_schema()
    )


@router.post("/reload", status_code=status.HTTP_202_ACCEPTED)
async def reload_plugins(
    _user: Annotated[User, Depends(get_current_user)],
) -> dict[str, Any]:
    plugin_registry.reload()
    return {"ok": True, "loaded": [p.name for p in plugin_registry.list()]}