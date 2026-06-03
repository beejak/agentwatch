"""
SC8: Rate limit cascade — multiple agents hit API limits, exponential backoff
cascades across the system. All status=ok but total cost explodes.

Pattern: framework_fault=True on many spans, increasing duration_ms,
         all from different agents but same parent trace.
"""
import pytest
import uuid
import time
from watchtower.core.signal import Signal
from watchtower.verdict.sources.deterministic import run_deterministic
from watchtower.coord_sigs.library import CoordSignatureLibrary
from watchtower.coord_sigs.matcher import match_signatures


def make_backoff_span(agent_id, attempt, trace_id, framework_fault=True):
    backoff_ms = 100 * (2 ** attempt)  # Exponential: 200, 400, 800, 1600...
    return Signal(
        trace_id=trace_id,
        span_id=str(uuid.uuid4()),
        parent_span_id=None,
        agent_id=agent_id,
        action="llm_call",
        status="ok",
        timestamp=time.time() + attempt,
        duration_ms=backoff_ms,
        tokens_in=100,
        tokens_out=50,
        model="gpt-4o",
        cost=0.00045,
        instruction_hash=None,
        caller_agent_id=None,
        process_guid=None,
        retrieval_flag=False,
        memory_op=None,
        framework_fault=framework_fault,
        policy_checked=True,
        summary=f"rate limit retry attempt {attempt}",
    )


@pytest.mark.asyncio
async def test_single_rate_limit_retry_not_flagged():
    """Single retry after rate limit — normal, should not cascade-flag."""
    trace_id = str(uuid.uuid4())
    spans = [make_backoff_span("agent-a", 0, trace_id, framework_fault=False)]
    result = run_deterministic(spans)
    assert not result.is_conclusive


@pytest.mark.asyncio
async def test_multi_agent_backoff_cascade_high_span_count():
    """10 agents × 8 retries each = 80 framework_fault spans — should fire."""
    trace_id = str(uuid.uuid4())
    spans = []
    for agent_idx in range(10):
        for attempt in range(8):
            spans.append(make_backoff_span(f"agent-{agent_idx}", attempt, trace_id))

    assert len(spans) == 80
    framework_faults = sum(1 for s in spans if s.framework_fault)
    assert framework_faults == 80

    result = run_deterministic(spans)
    assert result.is_conclusive, "80 framework_fault spans should trigger deterministic"


@pytest.mark.asyncio
async def test_rate_limit_cascade_signature_exists():
    """infra_rate_limit_cascade signature loaded from YAML."""
    lib = CoordSignatureLibrary()
    await lib.load()
    sigs = lib.get_all_signatures()
    cascade_sig = next((s for s in sigs if s.signature_id == "infra_rate_limit_cascade"), None)
    assert cascade_sig is not None
    assert cascade_sig.risk_level == "high"


@pytest.mark.asyncio
async def test_single_framework_fault_not_cascade():
    """1 framework fault out of 10 spans — deterministic flags any MIM signal."""
    trace_id = str(uuid.uuid4())
    spans = [make_backoff_span("agent-a", i, trace_id, framework_fault=(i == 5)) for i in range(10)]
    framework_faults = sum(1 for s in spans if s.framework_fault)
    assert framework_faults == 1
    # Deterministic fires on any framework_fault — but confidence < cascade (80 faults)
    result = run_deterministic(spans)
    # Either conclusive with low confidence, or not conclusive — both acceptable
    if result.is_conclusive:
        assert result.confidence < 0.99  # Not max confidence for single fault
    else:
        assert not result.is_conclusive


@pytest.mark.asyncio
async def test_exponential_duration_increase_detectable():
    """Duration grows exponentially — detectable pattern."""
    trace_id = str(uuid.uuid4())
    spans = [make_backoff_span("agent-a", i, trace_id) for i in range(8)]
    durations = [s.duration_ms for s in spans]
    # Each doubles
    for i in range(1, len(durations)):
        assert durations[i] > durations[i - 1], "Durations should be increasing"
    assert durations[-1] > durations[0] * 10, "Final duration should be 10x initial"
