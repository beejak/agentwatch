"""
SC2: Silent Failure Detection (the $47K scenario)
Proof question: Agent returns HTTP 200, no errors, but is in infinite retry loop.
Cost is 50x normal. Green dashboards everywhere. WatchTower catches it.

WatchTower must answer:
  - pattern = "infinite_retry_loop"
  - detected = True
  - cost_anomaly_ratio > 10
"""
import pytest



@pytest.mark.parametrize("trial", range(3))  # Pass^3
async def test_sc2_silent_failure_detected(trial, silent_failure_trace):
    """SC2: Infinite retry loop detected despite all spans showing status=ok."""
    from watchtower.analyst.silent import SilentFailureAgent
    from watchtower.baseline.engine import BaselineEngine

    trace_id, spans = silent_failure_trace

    # Verify: all spans have status=ok (this is the point — nothing looks wrong)
    assert all(s.status == "ok" for s in spans), \
        "SC2 test: all spans should be ok (silent failure means no errors)"

    # Build minimal baseline: normal agent costs ~$0.0009 per 3-span trace
    # Our looping agent: 150 spans at same rate = ~$0.045 (50x)
    baseline = BaselineEngine()
    await baseline.set_test_baseline("looping-agent", avg_cost=0.0009, avg_step_count=3.0)

    # Run silent failure detection
    analyst = SilentFailureAgent(baseline=baseline)
    result = await analyst.detect(trace_id=trace_id, spans=spans)

    print(f"\n[SC2 trial={trial}]")
    print(f"  detected:            {result.detected}")
    print(f"  pattern:             {result.pattern}")
    print(f"  cost_anomaly_ratio:  {result.cost_anomaly_ratio:.1f}x")
    print(f"  evidence:            {result.evidence}")

    assert result.detected, f"SC2 trial {trial}: silent failure not detected"
    assert result.pattern == "infinite_retry_loop", \
        f"Expected pattern='infinite_retry_loop', got '{result.pattern}'"
    assert result.cost_anomaly_ratio > 10, \
        f"Expected cost_anomaly_ratio > 10, got {result.cost_anomaly_ratio}"


async def test_sc2_langsmith_would_miss_this(silent_failure_trace):
    """
    Document the LangSmith gap for SC2.
    LangSmith shows: status=ok, latency=normal → GREEN DASHBOARD
    WatchTower shows: cost_anomaly_ratio=50x → ALERT
    """
    trace_id, spans = silent_failure_trace

    # Simulate what LangSmith sees
    langsmith_sees_error = any(s.status != "ok" for s in spans)
    langsmith_sees_latency_issue = any(s.duration_ms > 10000 for s in spans)

    # LangSmith would show green (no errors, normal latency per span)
    assert not langsmith_sees_error, "LangSmith baseline: no errors in spans"
    assert not langsmith_sees_latency_issue, "LangSmith baseline: latency normal per span"

    # But total cost is the signal
    total_cost = sum(s.cost for s in spans)
    assert total_cost > 0.01, f"SC2: total cost should be high, got {total_cost:.4f}"

    print(f"\n[SC2 Gap]")
    print(f"  LangSmith: no errors, normal latency → GREEN (misses it)")
    print(f"  WatchTower: total_cost={total_cost:.4f}, 50x normal → ALERT")
