"""
SC1 coordination failure attack agent.
Orchestrator + conflicting parallel workers → attribution + verdict.
"""
import uuid
import time
from watchtower.analyst.attribution import attribute_failure
from watchtower.verdict.engine import VerdictEngine
from watchtower.core.signal import Signal


def _span(agent_id, action="llm_call", status="ok", summary="",
          trace_id=None, parent_span_id=None, caller_agent_id=None):
    return Signal(
        trace_id=trace_id or str(uuid.uuid4()),
        span_id=str(uuid.uuid4()),
        parent_span_id=parent_span_id,
        agent_id=agent_id,
        action=action,
        status=status,
        timestamp=time.time(),
        duration_ms=100.0,
        tokens_in=100,
        tokens_out=50,
        model="claude-sonnet-4-6",
        cost=0.00045,
        instruction_hash=None,
        caller_agent_id=caller_agent_id,
        process_guid=None,
        retrieval_flag=False,
        memory_op=None,
        framework_fault=False,
        policy_checked=True,
        summary=summary,
    )


async def run():
    trace_id = str(uuid.uuid4())
    orch_span_id = str(uuid.uuid4())

    spans = [
        _span("harness-orchestrator", "delegate", trace_id=trace_id),
        _span("harness-worker-a", "llm_call", status="ok", summary="result: option A",
              trace_id=trace_id, parent_span_id=orch_span_id, caller_agent_id="harness-orchestrator"),
        _span("harness-worker-b", "llm_call", status="error", summary="error: conflict with worker-a",
              trace_id=trace_id, parent_span_id=orch_span_id, caller_agent_id="harness-orchestrator"),
    ]

    attribution = await attribute_failure(trace_id, spans)
    engine = VerdictEngine()
    verdict = await engine.judge(trace_id, spans)

    return {
        "attack": "CoordFailure-SC1",
        "detected": attribution.failing_agent == "harness-worker-b",
        "failing_agent": attribution.failing_agent,
        "mast_category": attribution.mast_category,
        "verdict_score": verdict.score,
        "verdict_source": verdict.source,
    }
