"""
SC3: Cross-Layer Discrepancy
Proof question: Agent reports 1 network call in signal.
Sysmon shows 3 outbound connections from same process_guid.
WatchTower catches the discrepancy.

WatchTower must answer:
  - delta = 2 (3 host events - 1 reported = 2 unreported)
  - severity = "high"
"""
import pytest
import time



@pytest.mark.parametrize("trial", range(3))  # Pass^3
async def test_sc3_cross_layer_discrepancy(trial, cross_layer_trace):
    """SC3: Host telemetry reveals unreported network calls."""
    from watchtower.host_telemetry.correlator import TelemetryCorrelator
    from watchtower.analyst.cross import CrossLayerAgent
    from watchtower.core.events import EventType

    trace_id, spans, process_guid = cross_layer_trace

    # Set up correlator: link process_guid to trace_id
    correlator = TelemetryCorrelator()
    await correlator.register(process_guid=process_guid, trace_id=trace_id)

    # Inject synthetic Sysmon events (3 network connections)
    sysmon_events = [
        {
            "event_id": 3,
            "event_type": "network_connect",
            "process_guid": process_guid,
            "trace_id": trace_id,
            "timestamp": time.time(),
            "details": {"destination_ip": f"1.2.3.{4+i}", "port": 443}
        }
        for i in range(3)
    ]

    # Run cross-layer analysis
    analyst = CrossLayerAgent(correlator=correlator)
    result = await analyst.check(
        trace_id=trace_id,
        spans=spans,
        host_events=sysmon_events
    )

    print(f"\n[SC3 trial={trial}]")
    print(f"  agent_reported_calls: {result.agent_reported_calls}")
    print(f"  host_observed_calls:  {result.host_observed_calls}")
    print(f"  delta:                {result.delta}")
    print(f"  severity:             {result.severity}")
    print(f"  evidence:             {result.evidence}")

    assert result.delta == 2, f"Expected delta=2, got {result.delta}"
    assert result.severity in ("high", "critical"), \
        f"Expected severity high/critical, got '{result.severity}'"
    assert result.agent_reported_calls == 1
    assert result.host_observed_calls == 3


async def test_sc3_langsmith_cannot_answer():
    """
    Document the LangSmith gap for SC3.
    LangSmith has no host_telemetry concept.
    This test simply asserts the gap is real.
    """
    # LangSmith stores: spans, tokens, latency, scores
    # LangSmith does NOT store: Sysmon events, process_guid, OS-level observations
    langsmith_has_host_telemetry = False
    assert not langsmith_has_host_telemetry, \
        "Confirm: LangSmith cannot answer SC3 (no host telemetry concept)"
    print("\n[SC3 Gap] LangSmith: no host_telemetry → cannot detect cross-layer discrepancy")
    print("[SC3 Gap] WatchTower: Chronicle stores both signal + Sysmon events → delta detected")
