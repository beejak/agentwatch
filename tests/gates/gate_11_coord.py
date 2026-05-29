"""Gate 11: Coordination Signatures — topology matching."""
import time
import uuid
import pytest

from watchtower.coord_sigs.library import CoordSignatureLibrary
from watchtower.core.signal import Signal


def make_span(**kwargs) -> Signal:
    return Signal(
        trace_id=kwargs.get("trace_id", str(uuid.uuid4())),
        span_id=kwargs.get("span_id", str(uuid.uuid4())),
        parent_span_id=kwargs.get("parent_span_id", None),
        agent_id=kwargs.get("agent_id", "test-agent"),
        action=kwargs.get("action", "llm_call"),
        status=kwargs.get("status", "ok"),
        timestamp=time.time(),
        duration_ms=100.0,
        cost=kwargs.get("cost", 0.001),
        summary=kwargs.get("summary", "test"),
    )


@pytest.fixture
async def library():
    lib = CoordSignatureLibrary()
    await lib.load()
    return lib


async def test_all_14_mast_modes_load(library):
    """All 14 MAST signatures should load without error."""
    mast_sigs = [s for s in library._signatures if s.get("_category", "").startswith("mast_")]
    assert len(mast_sigs) == 14, f"Expected 14 MAST signatures, found {len(mast_sigs)}"


async def test_parallel_workers_matches_conflicting_outputs(library):
    """Orchestrator → parallel workers with error → matches conflicting_parallel_outputs."""
    trace_id = str(uuid.uuid4())
    orch_span_id = str(uuid.uuid4())
    orch = make_span(agent_id="orchestrator", action="delegate", span_id=orch_span_id, trace_id=trace_id)
    worker_a = make_span(agent_id="worker-a", action="llm_call", parent_span_id=orch_span_id, trace_id=trace_id)
    worker_b = make_span(agent_id="worker-b", action="llm_call", parent_span_id=orch_span_id, status="error", trace_id=trace_id)
    spans = [orch, worker_a, worker_b]

    matches = await library.match_topology(spans)
    match_ids = [m.signature_id for m in matches]
    assert "mast_c2_conflicting_parallel_outputs" in match_ids


async def test_sequential_matches_no_feedback_loop(library):
    """Deep sequential chain → matches no_feedback_loop."""
    trace_id = str(uuid.uuid4())
    spans = []
    prev_id = None
    # Create chain A→B→C→D (depth 4)
    for i in range(4):
        span_id = str(uuid.uuid4())
        spans.append(make_span(
            agent_id=f"agent-{i}",
            action="llm_call",
            span_id=span_id,
            parent_span_id=prev_id,
            trace_id=trace_id,
        ))
        prev_id = span_id

    matches = await library.match_topology(spans)
    match_ids = [m.signature_id for m in matches]
    assert "mast_c3_no_feedback_loop" in match_ids


async def test_repeated_output_matches_infinite_retry(library):
    """Same summary repeated many times → matches infinite_retry_loop."""
    trace_id = str(uuid.uuid4())
    spans = [
        make_span(trace_id=trace_id, summary="retry: same output", cost=0.001)
        for _ in range(60)
    ]
    # Add some cost to trigger cost_anomaly_ratio_gt_10
    for s in spans:
        s.cost = 0.002

    matches = await library.match_topology(spans)
    match_ids = [m.signature_id for m in matches]
    assert "infra_infinite_retry_loop" in match_ids


async def test_match_has_risk_level_and_fix(library):
    """SignatureMatch must have risk_level + fix_direction populated."""
    trace_id = str(uuid.uuid4())
    orch_span_id = str(uuid.uuid4())
    orch = make_span(agent_id="orch", action="delegate", span_id=orch_span_id, trace_id=trace_id)
    w1 = make_span(agent_id="w1", action="llm_call", parent_span_id=orch_span_id, trace_id=trace_id, status="error")
    w2 = make_span(agent_id="w2", action="llm_call", parent_span_id=orch_span_id, trace_id=trace_id)

    matches = await library.match_topology([orch, w1, w2])
    assert len(matches) > 0
    for m in matches:
        assert m.risk_level in ("low", "medium", "high", "critical")
        assert m.fix_direction
        assert m.signature_id


async def test_clean_trace_fewer_matches(library):
    """A simple clean trace should match fewer (or no) critical signatures."""
    trace_id = str(uuid.uuid4())
    spans = [make_span(trace_id=trace_id, summary=f"step {i}") for i in range(3)]
    matches = await library.match_topology(spans)
    critical = [m for m in matches if m.risk_level == "critical"]
    assert len(critical) == 0
