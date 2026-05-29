"""Gate 12: Analyst — SC1/SC2/SC3 analysis."""
import time
import uuid
import pytest

from watchtower.analyst.manager import AnalystManager
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
        process_guid=kwargs.get("process_guid", None),
    )


@pytest.fixture
def manager():
    return AnalystManager()


async def test_sc1_attribute_failure_identifies_worker(manager):
    """SC1: attribute_failure() returns correct failing_agent=worker-b."""
    trace_id = str(uuid.uuid4())
    orch_id = str(uuid.uuid4())
    orch = make_span(agent_id="orchestrator", action="delegate", span_id=orch_id, trace_id=trace_id)
    worker_a = make_span(agent_id="worker-a", action="llm_call", parent_span_id=orch_id, trace_id=trace_id)
    worker_b = make_span(agent_id="worker-b", action="llm_call", parent_span_id=orch_id, status="error", trace_id=trace_id)

    manager.load_spans(trace_id, [orch, worker_a, worker_b])
    result = await manager.attribute_failure(trace_id)

    assert result.failing_agent == "worker-b"
    assert result.trace_id == trace_id


async def test_sc1_mast_category_2_for_parallel_conflict(manager):
    """SC1: mast_category=2 for conflicting parallel outputs scenario."""
    trace_id = str(uuid.uuid4())
    orch_id = str(uuid.uuid4())
    orch = make_span(agent_id="orchestrator", action="delegate", span_id=orch_id, trace_id=trace_id)
    worker_a = make_span(agent_id="worker-a", parent_span_id=orch_id, trace_id=trace_id)
    worker_b = make_span(agent_id="worker-b", parent_span_id=orch_id, status="error", trace_id=trace_id)

    manager.load_spans(trace_id, [orch, worker_a, worker_b])
    result = await manager.attribute_failure(trace_id)

    assert result.mast_category == 2


async def test_sc2_detect_silent_failure(manager):
    """SC2: detect_silent_failure() returns detected=True for infinite retry trace."""
    trace_id = str(uuid.uuid4())
    # 150 spans with same summary, no errors
    spans = [
        make_span(trace_id=trace_id, summary="retry attempt: same output", cost=0.001)
        for _ in range(150)
    ]
    manager.load_spans(trace_id, spans)
    result = await manager.detect_silent_failure(trace_id)

    assert result.detected is True
    assert result.trace_id == trace_id


async def test_sc3_cross_layer_delta(manager):
    """SC3: check_cross_layer() returns delta>0 when host sees more connections."""
    trace_id = str(uuid.uuid4())
    process_guid = str(uuid.uuid4())

    # Agent reports 1 API call
    span = make_span(
        agent_id="suspicious-agent",
        action="api_call",
        trace_id=trace_id,
        process_guid=process_guid,
    )
    manager.load_spans(trace_id, [span])

    # Host telemetry shows 3 network connections
    host_events = [
        {"process_guid": process_guid, "event_type": "NetworkConnect"}
        for _ in range(3)
    ]
    manager.load_host_telemetry(trace_id, host_events)

    result = await manager.check_cross_layer(trace_id)
    assert result.delta > 0
    assert result.agent_reported_calls == 1
    assert result.host_observed_calls == 3


async def test_full_report_has_all_sections(manager):
    """full_report() returns all three results in one dict."""
    trace_id = str(uuid.uuid4())
    orch_id = str(uuid.uuid4())
    spans = [
        make_span(agent_id="orchestrator", span_id=orch_id, trace_id=trace_id),
        make_span(agent_id="worker", parent_span_id=orch_id, status="error", trace_id=trace_id),
    ]
    manager.load_spans(trace_id, spans)
    report = await manager.full_report(trace_id)

    assert "attribution" in report
    assert "silent_failure" in report
    assert "cross_layer" in report
    assert report["trace_id"] == trace_id


async def test_attribution_result_has_fix_direction(manager):
    """AttributionResult must have fix_direction populated."""
    trace_id = str(uuid.uuid4())
    spans = [
        make_span(agent_id="agent-a", status="error", trace_id=trace_id),
    ]
    manager.load_spans(trace_id, spans)
    result = await manager.attribute_failure(trace_id)
    assert result.fix_direction
    assert result.confidence > 0
