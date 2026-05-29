"""Gate 10: Behavioral Baseline — agent profiling and deviation detection."""
import time
import uuid
import pytest

from watchtower.baseline.engine import BaselineEngine
from watchtower.baseline.profile import AgentProfile


def make_span(agent_id="agent-a", action="llm_call", cost=0.001, duration_ms=200.0, summary="step"):
    from watchtower.core.signal import Signal
    return Signal(
        trace_id=str(uuid.uuid4()),
        span_id=str(uuid.uuid4()),
        agent_id=agent_id,
        action=action,
        status="ok",
        timestamp=time.time(),
        duration_ms=duration_ms,
        tokens_in=100,
        tokens_out=50,
        cost=cost,
        summary=summary,
    )


@pytest.fixture
async def engine_with_history():
    """Build a baseline engine with 60 historical traces for agent-a."""
    engine = BaselineEngine()
    # Add 60 traces of 5 spans each (consistent baseline)
    for _ in range(60):
        spans = [make_span(cost=0.001, duration_ms=200.0) for _ in range(5)]
        await engine.update_profile("agent-a", spans)
    return engine


async def test_profile_builds_from_history(engine_with_history):
    profile = await engine_with_history.build_profile("agent-a")
    assert profile.trace_count >= 60
    assert profile.avg_step_count > 0


async def test_restricted_mode_for_new_agent():
    engine = BaselineEngine()
    # Only 5 traces (< 50 threshold)
    for _ in range(5):
        spans = [make_span() for _ in range(3)]
        await engine.update_profile("new-agent", spans)
    assert await engine.is_restricted("new-agent") is True


async def test_not_restricted_after_50_traces():
    engine = BaselineEngine()
    for _ in range(55):
        spans = [make_span() for _ in range(3)]
        await engine.update_profile("veteran-agent", spans)
    assert await engine.is_restricted("veteran-agent") is False


async def test_deviation_detected_on_step_count(engine_with_history):
    """Step count > avg + 3*std should be flagged."""
    # Baseline is 5 spans per trace, std~=0, avg=5
    # Give it 100 spans — well above threshold
    anomalous_spans = [make_span() for _ in range(100)]
    deviation = await engine_with_history.check_deviation("agent-a", anomalous_spans)
    assert deviation is not None
    assert "step" in deviation.lower() or "count" in deviation.lower() or "exceed" in deviation.lower()


async def test_no_deviation_for_normal_trace(engine_with_history):
    """Normal trace should return None."""
    normal_spans = [make_span() for _ in range(5)]
    deviation = await engine_with_history.check_deviation("agent-a", normal_spans)
    assert deviation is None


async def test_update_profile_changes_stats():
    engine = BaselineEngine()
    # Start with 10 short traces
    for _ in range(10):
        await engine.update_profile("evolving-agent", [make_span(cost=0.001)])

    profile_before = await engine.build_profile("evolving-agent")
    assert profile_before.avg_step_count == 1.0

    # Update with longer traces
    for _ in range(10):
        await engine.update_profile("evolving-agent", [make_span() for _ in range(10)])

    profile_after = await engine.build_profile("evolving-agent")
    # Average should have shifted toward larger step count
    assert profile_after.avg_step_count > profile_before.avg_step_count


async def test_unknown_agent_no_crash():
    engine = BaselineEngine()
    deviation = await engine.check_deviation("unknown-agent-xyz", [make_span()])
    # Should return None (no baseline, not anomalous by default)
    assert deviation is None
