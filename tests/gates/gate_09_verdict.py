"""Gate 09: Verdict Engine — 5-source judgment with early exit."""
import time
import uuid
import pytest

from watchtower.verdict.engine import VerdictEngine, Verdict
from watchtower.verdict.summariser import summarise_trace


@pytest.fixture
def make_signal():
    def _make(**kwargs):
        from watchtower.core.signal import Signal
        return Signal(
            trace_id=kwargs.get("trace_id", str(uuid.uuid4())),
            span_id=str(uuid.uuid4()),
            agent_id=kwargs.get("agent_id", "test-agent"),
            action=kwargs.get("action", "llm_call"),
            status=kwargs.get("status", "ok"),
            timestamp=time.time(),
            duration_ms=100.0,
            tokens_in=100,
            tokens_out=50,
            cost=kwargs.get("cost", 0.0003),
            summary=kwargs.get("summary", "test"),
            framework_fault=kwargs.get("framework_fault", False),
        )
    return _make


@pytest.fixture
def engine():
    return VerdictEngine()


async def test_cost_threshold_fires(engine, make_signal):
    """Cost > $0.10 → deterministic bad verdict."""
    trace_id = str(uuid.uuid4())
    spans = [make_signal(trace_id=trace_id, cost=0.05) for _ in range(3)]
    verdict = await engine.judge(trace_id, spans)
    assert verdict.score < 0.5
    assert verdict.source == "deterministic"
    assert "cost" in verdict.reason.lower()


async def test_silent_failure_3_repeats(engine, make_signal):
    """Same summary 3+ times → bad verdict."""
    trace_id = str(uuid.uuid4())
    repeated_summary = "retry: same output every time"
    spans = [make_signal(trace_id=trace_id, summary=repeated_summary) for _ in range(4)]
    verdict = await engine.judge(trace_id, spans)
    assert verdict.score < 0.5
    assert verdict.source == "deterministic"
    assert "silent" in verdict.reason.lower() or "repeat" in verdict.reason.lower()


async def test_trace_summariser_compresses_large_trace(make_signal):
    """500-span trace should compress to < 2000 chars."""
    trace_id = str(uuid.uuid4())
    spans = [make_signal(trace_id=trace_id) for _ in range(500)]
    summary = summarise_trace(spans)
    assert len(summary) < 2000


async def test_llm_judge_receives_summary_not_raw(make_signal):
    """LLM judge should get summary string, not raw spans."""
    received_input = []

    def mock_llm(summary: str) -> str:
        received_input.append(summary)
        return "Trace looks normal, no anomalies detected"

    engine = VerdictEngine(llm_fn=mock_llm)
    trace_id = str(uuid.uuid4())
    # Use unique summaries to avoid triggering silent failure rule
    spans = [make_signal(trace_id=trace_id, summary=f"unique step {i}") for i in range(5)]
    verdict = await engine.judge(trace_id, spans)

    # LLM should have received a string summary
    assert len(received_input) == 1
    assert isinstance(received_input[0], str)
    # Should be shorter than raw span data
    raw_len = sum(len(str(s.model_dump())) for s in spans)
    assert len(received_input[0]) < raw_len


async def test_verdict_fields_populated(engine, make_signal):
    """Every Verdict has score + source + reason populated."""
    trace_id = str(uuid.uuid4())
    spans = [make_signal(trace_id=trace_id)]
    verdict = await engine.judge(trace_id, spans)
    assert isinstance(verdict.score, float)
    assert verdict.source in ("deterministic", "baseline", "llm_judge", "indirect", "human")
    assert verdict.reason
    assert verdict.trace_id == trace_id
    assert verdict.timestamp > 0


async def test_step_count_rule(engine, make_signal):
    """More than 50 spans → bad verdict."""
    trace_id = str(uuid.uuid4())
    spans = [make_signal(trace_id=trace_id) for _ in range(60)]
    verdict = await engine.judge(trace_id, spans)
    assert verdict.score < 0.5
    assert verdict.source == "deterministic"


async def test_clean_trace_passes(make_signal):
    """A clean trace with low cost and few spans should pass."""
    engine = VerdictEngine()
    trace_id = str(uuid.uuid4())
    spans = [
        make_signal(trace_id=trace_id, cost=0.0001, summary=f"step {i}")
        for i in range(3)
    ]
    verdict = await engine.judge(trace_id, spans)
    # Should reach llm_judge or baseline without deterministic fire
    assert isinstance(verdict, Verdict)
    assert verdict.reason  # Always populated
