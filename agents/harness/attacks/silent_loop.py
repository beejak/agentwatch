"""
Silent loop attack agent.
Generates 150 identical ok-status spans — the $47K scenario.
"""
import uuid
import time
from watchtower.analyst.silent import detect_silent_failure
from watchtower.core.signal import Signal


def _span(trace_id):
    return Signal(
        trace_id=trace_id,
        span_id=str(uuid.uuid4()),
        parent_span_id=None,
        agent_id="harness-looping-agent",
        action="llm_call",
        status="ok",
        timestamp=time.time(),
        duration_ms=100.0,
        tokens_in=100,
        tokens_out=50,
        model="claude-sonnet-4-6",
        cost=0.00045,
        instruction_hash=None,
        caller_agent_id=None,
        process_guid=None,
        retrieval_flag=False,
        memory_op=None,
        framework_fault=False,
        policy_checked=True,
        summary="retry attempt: same output repeated",
    )


async def run(span_count: int = 150):
    trace_id = str(uuid.uuid4())
    spans = [_span(trace_id) for _ in range(span_count)]

    result = await detect_silent_failure(trace_id, spans)
    return {
        "attack": "SilentLoop",
        "detected": result.detected,
        "pattern": result.pattern,
        "cost_anomaly_ratio": result.cost_anomaly_ratio,
        "span_count": span_count,
        "projected_hourly_cost": span_count * 0.00045 * 60,
    }
