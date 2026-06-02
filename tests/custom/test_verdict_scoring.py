"""Custom tests — verdict scoring correctness (0.0=bad, 1.0=good)."""
from __future__ import annotations

import time
import uuid

import pytest

from watchtower.core.signal import Signal
from watchtower.verdict.engine import VerdictEngine


def _span(summary="ok action", status="ok", cost=0.0, framework_fault=False):
    return Signal(
        trace_id=str(uuid.uuid4()),
        agent_id="test-agent",
        action="llm_call",
        status=status,
        summary=summary,
        cost=cost,
        framework_fault=framework_fault,
    )


@pytest.mark.asyncio
async def test_cost_explosion_scores_zero():
    engine = VerdictEngine()
    spans = [_span(cost=0.05) for _ in range(3)]  # total $0.15 > threshold
    verdict = await engine.judge(str(uuid.uuid4()), spans)
    assert verdict.score == 0.0
    assert verdict.source == "deterministic"


@pytest.mark.asyncio
async def test_clean_trace_scores_high():
    engine = VerdictEngine()
    spans = [_span(summary=f"step {i}", cost=0.0001) for i in range(5)]
    verdict = await engine.judge(str(uuid.uuid4()), spans)
    assert verdict.score >= 0.5
    assert verdict.score <= 1.0


@pytest.mark.asyncio
async def test_silent_failure_scores_zero():
    engine = VerdictEngine()
    spans = [_span(summary="retry attempt: same output repeated") for _ in range(5)]
    verdict = await engine.judge(str(uuid.uuid4()), spans)
    assert verdict.score == 0.0
    assert "silent failure" in verdict.reason.lower()


@pytest.mark.asyncio
async def test_mim_flag_scores_zero():
    engine = VerdictEngine()
    spans = [_span(framework_fault=True)]
    verdict = await engine.judge(str(uuid.uuid4()), spans)
    assert verdict.score == 0.0


@pytest.mark.asyncio
async def test_verdict_always_has_reason():
    engine = VerdictEngine()
    for _ in range(5):
        spans = [_span()]
        verdict = await engine.judge(str(uuid.uuid4()), spans)
        assert verdict.reason


@pytest.mark.asyncio
async def test_verdict_always_has_source():
    engine = VerdictEngine()
    spans = [_span()]
    verdict = await engine.judge(str(uuid.uuid4()), spans)
    assert verdict.source in {"deterministic", "baseline", "llm_judge", "indirect", "human"}


@pytest.mark.asyncio
async def test_llm_fn_bad_response_scores_low():
    """LLM saying 'suspicious' → score 0.0."""
    async def mock_llm(summary):
        return "This trace is suspicious and malicious."

    engine = VerdictEngine(llm_fn=mock_llm)
    spans = [_span(summary=f"step {i}") for i in range(3)]
    verdict = await engine.judge(str(uuid.uuid4()), spans)
    assert verdict.score == 0.0
    assert verdict.source == "llm_judge"


@pytest.mark.asyncio
async def test_llm_fn_clean_response_scores_high():
    """LLM saying 'clean' → score 1.0."""
    async def mock_llm(summary):
        return "This trace looks completely normal and clean."

    engine = VerdictEngine(llm_fn=mock_llm)
    spans = [_span(summary=f"step {i}") for i in range(3)]
    verdict = await engine.judge(str(uuid.uuid4()), spans)
    assert verdict.score == 1.0


@pytest.mark.asyncio
async def test_empty_trace_returns_verdict():
    engine = VerdictEngine()
    verdict = await engine.judge(str(uuid.uuid4()), [])
    assert verdict.score is not None
    assert verdict.reason


@pytest.mark.asyncio
async def test_llm_judge_receives_summary_not_raw_spans():
    """LLM judge must receive summarised text, not span objects."""
    received = []

    async def capture_llm(summary: str):
        received.append(summary)
        return "clean trace"

    engine = VerdictEngine(llm_fn=capture_llm)
    spans = [_span(summary=f"action {i}") for i in range(5)]
    await engine.judge(str(uuid.uuid4()), spans)

    assert received, "LLM was not called"
    assert isinstance(received[0], str), "LLM received non-string"
    # Must be a compressed summary, not raw span list
    assert "Signal" not in received[0]
    assert len(received[0]) < 5000
