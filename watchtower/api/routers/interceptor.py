"""Interceptor router — quarantine and halt endpoints."""
from __future__ import annotations

import os

from fastapi import APIRouter, Depends, HTTPException, Security
from fastapi.security import APIKeyHeader

from watchtower.api.schemas.responses import QuarantineRequest, QuarantineResponse
from watchtower.interceptor.interceptor import Interceptor

router = APIRouter(prefix="/api/v1/interceptor", tags=["interceptor"])

_interceptor = Interceptor()

_API_KEY_HEADER = APIKeyHeader(name="X-WatchTower-Key", auto_error=False)
_WATCHTOWER_KEY = os.getenv("WATCHTOWER_API_KEY", "")


async def _require_api_key(key: str | None = Security(_API_KEY_HEADER)) -> str:
    if not _WATCHTOWER_KEY:
        return ""  # No key configured — open (dev mode)
    if not key or key != _WATCHTOWER_KEY:
        raise HTTPException(status_code=403, detail="Invalid or missing API key")
    return key


@router.post("/quarantine", response_model=QuarantineResponse)
async def trigger_quarantine(
    request: QuarantineRequest,
    _: str = Depends(_require_api_key),
):
    """Trigger quarantine for an agent. Requires X-WatchTower-Key header when WATCHTOWER_API_KEY is set."""
    action = await _interceptor.quarantine(
        agent_id=request.agent_id,
        reason=request.reason,
        trigger=request.trigger,
    )
    return QuarantineResponse(
        action_id=action.action_id,
        target_agent=action.target_agent,
        blast_radius=action.blast_radius,
        reason=action.reason,
        logged=action.logged,
    )
