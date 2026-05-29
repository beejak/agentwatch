"""Analyst router — SC1/SC2/SC3 analysis endpoints."""
from __future__ import annotations

from fastapi import APIRouter
from watchtower.api.schemas.responses import MarkdownReport, SilentFailureItem, TopologyRiskItem

router = APIRouter(prefix="/api/v1/analyst", tags=["analyst"])


@router.get("/report/{trace_id}", response_model=MarkdownReport)
async def get_analyst_report(trace_id: str):
    """Full analyst report: SC1 + SC2 + SC3 analysis."""
    from watchtower.api.main import get_reader, get_analyst
    reader = get_reader()
    analyst = get_analyst()

    # Get spans for this trace
    spans = []
    if reader:
        spans = await reader.get_trace(trace_id)

    # Build markdown report
    sc1 = sc2 = sc3 = None

    if analyst:
        analyst.load_spans(trace_id, spans)
        sc1 = (await analyst.attribute_failure(trace_id)).model_dump()
        sc2 = (await analyst.detect_silent_failure(trace_id)).model_dump()
        sc3 = (await analyst.check_cross_layer(trace_id)).model_dump()

    # Build markdown
    lines = [
        f"# WatchTower Analyst Report",
        f"",
        f"**Trace ID**: `{trace_id}`",
        f"**Spans**: {len(spans)}",
        f"",
    ]

    if sc1:
        lines += [
            f"## SC1: Coordination Failure Attribution",
            f"- **Failing Agent**: `{sc1.get('failing_agent', 'unknown')}`",
            f"- **MAST Category**: {sc1.get('mast_category', '?')}",
            f"- **Signature**: {sc1.get('signature_name', '?')}",
            f"- **Fix**: {sc1.get('fix_direction', '?')}",
            f"",
        ]

    if sc2:
        lines += [
            f"## SC2: Silent Failure Detection",
            f"- **Detected**: {sc2.get('detected', False)}",
            f"- **Pattern**: `{sc2.get('pattern', 'none')}`",
            f"- **Evidence**: {sc2.get('evidence', '')}",
            f"",
        ]

    if sc3:
        lines += [
            f"## SC3: Cross-Layer Discrepancy",
            f"- **Agent Reported**: {sc3.get('agent_reported_calls', 0)} calls",
            f"- **Host Observed**: {sc3.get('host_observed_calls', 0)} connections",
            f"- **Delta**: {sc3.get('delta', 0)}",
            f"- **Severity**: {sc3.get('severity', 'none')}",
            f"",
        ]

    return MarkdownReport(
        trace_id=trace_id,
        markdown_report="\n".join(lines),
        sc1_result=sc1,
        sc2_result=sc2,
        sc3_result=sc3,
    )


@router.get("/silent-failures", response_model=list[SilentFailureItem])
async def get_silent_failures(hours: int = 24):
    """Get silent failure report for the last N hours."""
    from watchtower.api.main import get_reader
    reader = get_reader()
    if reader is None:
        return []
    rows = await reader.get_silent_failures(hours=hours)
    return [
        SilentFailureItem(
            trace_id=row.get("trace_id", ""),
            agent_id=row.get("agent_id", ""),
            status=row.get("status", ""),
            summary=row.get("summary", ""),
            timestamp=float(row.get("timestamp", 0)),
        )
        for row in rows
    ]


@router.get("/topology-risks", response_model=list[TopologyRiskItem])
async def get_topology_risks():
    """Get active coordination signature matches."""
    from watchtower.coord_sigs.library import CoordSignatureLibrary
    lib = CoordSignatureLibrary()
    await lib.load()
    sigs = lib.get_all_signatures()
    return [
        TopologyRiskItem(
            signature_id=s.signature_id,
            name=s.name,
            risk_level=s.risk_level,
            description=s.description,
        )
        for s in sigs
    ]
