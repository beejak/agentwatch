"""Interceptor router — quarantine and halt endpoints."""
from __future__ import annotations

from fastapi import APIRouter
from watchtower.api.schemas.responses import QuarantineRequest, QuarantineResponse
from watchtower.interceptor.interceptor import Interceptor

router = APIRouter(prefix="/api/v1/interceptor", tags=["interceptor"])

_interceptor = Interceptor()


@router.post("/quarantine", response_model=QuarantineResponse)
async def trigger_quarantine(request: QuarantineRequest):
    """Trigger quarantine for an agent."""
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
