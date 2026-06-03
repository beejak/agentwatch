"""
SC7: Context window overflow / token burn attack.

Agent accumulates massive context (tokens_in >> normal). Verdict engine
deterministic + baseline stages must catch before it costs thousands.
"""
import pytest
import uuid
import time
from watchtower.core.signal import Signal
from watchtower.verdict.sources.deterministic import run_deterministic
from watchtower.verdict.engine import VerdictEngine


def make_span(tokens_in, tokens_out, cost=None, trace_id=None):
    cost = cost or (tokens_in + tokens_out) * 0.000003
    return Signal(
        trace_id=trace_id or str(uuid.uuid4()),
        span_id=str(uuid.uuid4()),
        parent_span_id=None,
        agent_id="context-hog-agent",
        action="llm_call",
        status="ok",
        timestamp=time.time(),
        duration_ms=500.0,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        model="gpt-4o",
        cost=cost,
        instruction_hash=None,
        caller_agent_id=None,
        process_guid=None,
        retrieval_flag=True,  # RAG is common cause
        memory_op=None,
        framework_fault=False,
        policy_checked=True,
        summary="llm call with accumulated context",
    )


@pytest.mark.asyncio
async def test_normal_token_usage_not_flagged():
    """100 tokens in, 50 out — normal, should not flag."""
    spans = [make_span(100, 50) for i in range(5)]
    # Unique summaries to avoid repeated-summary rule
    for i, s in enumerate(spans):
        object.__setattr__(s, "summary", f"processed item {i}")
    result = run_deterministic(spans)
    assert not result.is_conclusive


@pytest.mark.asyncio
async def test_extreme_token_burn_flagged_by_deterministic():
    """Single span with 200k tokens in, 1k out = $0.60 — deterministic must fire."""
    spans = [make_span(200_000, 1_000, cost=0.603)]
    result = run_deterministic(spans)
    assert result.is_conclusive
    assert result.confidence > 0.5


@pytest.mark.asyncio
async def test_accumulating_context_flagged():
    """
    Context grows span-by-span (context stuffing pattern).
    Cumulative cost exceeds threshold.
    """
    trace_id = str(uuid.uuid4())
    spans = []
    for i in range(10):
        # Each span adds 10k tokens (context accumulation)
        tokens_in = 10_000 * (i + 1)
        spans.append(make_span(tokens_in, 500, trace_id=trace_id))

    total_cost = sum(s.cost for s in spans)
    assert total_cost > 1.0  # Sanity check

    result = run_deterministic(spans)
    assert result.is_conclusive, f"Total cost ${total_cost:.2f} should trigger deterministic"


@pytest.mark.asyncio
async def test_verdict_engine_catches_token_burn():
    """Full verdict engine pipeline catches token burn at stage 1."""
    engine = VerdictEngine()
    trace_id = str(uuid.uuid4())
    spans = [make_span(500_000, 5_000, cost=1.515, trace_id=trace_id)]
    verdict = await engine.judge(trace_id, spans)
    assert verdict.score == 0.0
    assert verdict.source == "deterministic"


@pytest.mark.asyncio
async def test_infra_context_overflow_signature_loaded():
    """infra_context_window_overflow signature exists in library."""
    from watchtower.coord_sigs.library import CoordSignatureLibrary
    lib = CoordSignatureLibrary()
    await lib.load()
    sigs = lib.get_all_signatures()
    overflow_sig = next((s for s in sigs if s.signature_id == "infra_context_window_overflow"), None)
    assert overflow_sig is not None, "infra_context_window_overflow not in library"
    assert overflow_sig.risk_level == "high"
