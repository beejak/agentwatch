"""Traces router — Chronicle query endpoints."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from watchtower.api.schemas.responses import TraceResponse, VerdictResponse

router = APIRouter(prefix="/api/v1", tags=["traces"])


@router.get("/traces/{trace_id}", response_model=TraceResponse)
async def get_trace(trace_id: str):
    """Get full trace reconstruction from Chronicle."""
    from watchtower.api.main import get_reader
    reader = get_reader()
    if reader is None:
        return TraceResponse(trace_id=trace_id, span_count=0, spans=[])
    spans = await reader.get_trace(trace_id)
    return TraceResponse(
        trace_id=trace_id,
        span_count=len(spans),
        spans=spans,
    )


@router.get("/agents/{agent_id}/verdicts", response_model=list[VerdictResponse])
async def get_agent_verdicts(agent_id: str, limit: int = 50):
    """Get latest verdicts for an agent."""
    from watchtower.api.main import get_reader
    reader = get_reader()
    if reader is None:
        return []
    rows = await reader.get_agent_verdicts(agent_id, limit=limit)
    return [
        VerdictResponse(
            trace_id=row.get("trace_id", ""),
            agent_id=row.get("agent_id", agent_id),
            timestamp=row.get("timestamp"),
            details=str(row.get("details", "")),
        )
        for row in rows
    ]
