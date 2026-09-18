"""Preset Vault and Configuration Lifecycle API Router.

Extracted from strategies router for modularity and maintainability.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel

from kalshi_sim.preset_manager import get_preset_manager

logger = logging.getLogger("kalshi_sim.routers.presets")

router = APIRouter(tags=["presets"])

_state_getter = None


def init_presets_router(state_getter=None):
    global _state_getter
    _state_getter = state_getter


def get_state():
    if _state_getter is not None:
        return _state_getter()
    from kalshi_sim.server import state
    return state


class _StateProxy:
    def __getattr__(self, name):
        return getattr(get_state(), name)

    def __setattr__(self, name, value):
        setattr(get_state(), name, value)


state = _StateProxy()


class SavePresetRequest(BaseModel):
    preset_name: str
    description: Optional[str] = ""
    author: Optional[str] = "Operator"


class LoadPresetRequest(BaseModel):
    preset_id: str


class ImportPresetRequest(BaseModel):
    preset_json: Optional[str] = None
    preset_data: Optional[dict[str, Any]] = None
    apply_immediately: bool = False


@router.get("/api/bot/presets")
async def get_bot_presets_endpoint() -> dict[str, Any]:
    """List all presets in the vault and return active preset metadata."""
    pm = get_preset_manager()
    return {
        "status": "SUCCESS",
        "presets": pm.list_presets(),
        "active_preset": pm.get_active_preset_metadata(),
    }


@router.post("/api/bot/presets/save")
async def save_bot_preset_endpoint(req: SavePresetRequest) -> dict[str, Any]:
    """Snapshot current parameters into a new preset."""
    pm = get_preset_manager()
    success, msg, data = pm.save_preset(
        preset_name=req.preset_name,
        description=req.description or "",
        author=req.author or "Operator",
    )
    if not success:
        raise HTTPException(status_code=422, detail=msg)
    state.is_dirty = True
    return {"status": "SUCCESS", "message": msg, "preset": data}


@router.post("/api/bot/presets/load")
async def load_bot_preset_endpoint(req: LoadPresetRequest) -> dict[str, Any]:
    """Atomically load and hot-swap parameters from a preset into the engine."""
    pm = get_preset_manager()
    success, msg, data = pm.load_preset(req.preset_id)
    if not success:
        raise HTTPException(status_code=422, detail=msg)
    state.is_dirty = True
    return {"status": "SUCCESS", "message": msg, "active_preset": pm.get_active_preset_metadata()}


@router.post("/api/bot/presets/unload")
async def unload_bot_preset_endpoint() -> dict[str, Any]:
    """Revert configuration back to the Council Certified Baseline."""
    pm = get_preset_manager()
    success, msg, data = pm.unload_preset()
    if not success:
        raise HTTPException(status_code=422, detail=msg)
    state.is_dirty = True
    return {"status": "SUCCESS", "message": msg, "active_preset": pm.get_active_preset_metadata()}


@router.post("/api/bot/presets/upload")
async def upload_bot_preset_endpoint(req: ImportPresetRequest) -> dict[str, Any]:
    """Validate and import an uploaded preset JSON into the vault."""
    pm = get_preset_manager()
    raw_json = req.preset_json
    if not raw_json and req.preset_data:
        raw_json = json.dumps(req.preset_data)
    if not raw_json:
        raise HTTPException(status_code=400, detail="Missing preset_json or preset_data in request body")

    success, msg, data = pm.import_preset_json(raw_json)
    if not success:
        raise HTTPException(status_code=422, detail=msg)

    if req.apply_immediately:
        pm.load_preset(data["preset_id"])

    state.is_dirty = True
    return {"status": "SUCCESS", "message": msg, "preset": data}


@router.get("/api/bot/presets/export/{preset_id}")
async def export_bot_preset_endpoint(preset_id: str) -> Response:
    """Export a preset as a downloadable JSON file."""
    pm = get_preset_manager()
    data = pm.export_preset(preset_id)
    if not data:
        raise HTTPException(status_code=404, detail=f"Preset '{preset_id}' not found")
    content = json.dumps(data, indent=2)
    return Response(
        content=content,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{preset_id}.json"'},
    )


@router.delete("/api/bot/presets/{preset_id}")
async def delete_bot_preset_endpoint(preset_id: str) -> dict[str, Any]:
    """Delete a custom preset from the vault."""
    pm = get_preset_manager()
    success, msg = pm.delete_preset(preset_id)
    if not success:
        raise HTTPException(status_code=400, detail=msg)
    state.is_dirty = True
    return {"status": "SUCCESS", "message": msg}
