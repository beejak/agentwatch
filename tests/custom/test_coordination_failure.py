"""Custom tests — Coordination failure detection (Proof Q1, SC1)."""
from __future__ import annotations

import uuid

import pytest

from watchtower.core.signal import Signal
from watchtower.coord_sigs.library import CoordSignatureLibrary
from watchtower.analyst.attribution import attribute_failure


def _signal(agent_id, action, status="ok", summary="", caller_agent_id=None, trace_id=None):
    return Signal(
        trace_id=trace_id or str(uuid.uuid4()),
        agent_id=agent_id,
        action=action,
        status=status,
        summary=summary,
        caller_agent_id=caller_agent_id,
    )


@pytest.fixture
def sc1_trace():
    trace_id = str(uuid.uuid4())
    orch = _signal("orchestrator", "delegate", summary="delegate to workers", trace_id=trace_id)
    wa = _signal("worker-a", "llm_call", summary="result: option A", caller_agent_id="orchestrator", trace_id=trace_id)
    wb = _signal("worker-b", "llm_call", status="error", summary="error: conflicting instruction", caller_agent_id="orchestrator", trace_id=trace_id)
    return trace_id, [orch, wa, wb]


@pytest.mark.asyncio
async def test_parallel_conflict_signature_matches(sc1_trace):
    trace_id, spans = sc1_trace
    library = CoordSignatureLibrary()
    matches = await library.match_topology(spans)
    sig_ids = [m.signature_id for m in matches]
    assert len(matches) > 0, "Expected at least one signature match for SC1 trace"
    # SC1 involves error status, caller chain — some signature should match
    assert sig_ids


@pytest.mark.asyncio
async def test_sc1_analyst_identifies_worker_b(sc1_trace):
    trace_id, spans = sc1_trace
    result = await attribute_failure(trace_id, spans)
    assert result is not None
    assert "worker-b" in result.failing_agent


@pytest.mark.asyncio
async def test_sc1_attribution_has_fix_direction(sc1_trace):
    trace_id, spans = sc1_trace
    result = await attribute_failure(trace_id, spans)
    assert result.fix_direction is not None


@pytest.mark.asyncio
async def test_clean_trace_no_high_risk_match():
    trace_id = str(uuid.uuid4())
    spans = [
        _signal("agent-a", "llm_call", summary="step 1", trace_id=trace_id),
        _signal("agent-a", "tool_use", summary="step 2", trace_id=trace_id),
        _signal("agent-a", "handoff", summary="done", trace_id=trace_id),
    ]
    library = CoordSignatureLibrary()
    matches = await library.match_topology(spans)
    high_risk = [m for m in matches if m.risk_level == "high"]
    assert len(high_risk) == 0


@pytest.mark.asyncio
async def test_all_14_mast_modes_in_library():
    library = CoordSignatureLibrary()
    await library.load()
    sigs = library.get_all_signatures()
    assert len(sigs) >= 14, f"Expected ≥14 MAST signatures, got {len(sigs)}"


def test_sc1_error_agent_in_call_tree(sc1_trace):
    trace_id, spans = sc1_trace
    error_spans = [s for s in spans if s.status == "error"]
    assert len(error_spans) == 1
    assert error_spans[0].agent_id == "worker-b"
    assert error_spans[0].caller_agent_id == "orchestrator"


@pytest.mark.asyncio
async def test_sc1_attribution_mast_category_assigned(sc1_trace):
    trace_id, spans = sc1_trace
    result = await attribute_failure(trace_id, spans)
    assert result.mast_category in {1, 2, 3}
