"""SC3: Cross-layer discrepancy detection — host telemetry vs agent reports."""
from __future__ import annotations

from pydantic import BaseModel

# Network event types from various sources
NETWORK_EVENT_TYPES = {
    "NetworkConnect", "network_connect", "tcp_connect",
    "NetworkConnection", "network_connection",
}

# Agent actions that represent outbound network calls
AGENT_NETWORK_ACTIONS = {
    "api_call", "network_call", "http_request", "tool_use",
    "tcp_connect", "network_connect",
}


class CrossLayerResult(BaseModel):
    trace_id: str
    agent_reported_calls: int
    host_observed_calls: int
    delta: int
    severity: str       # "none","low","medium","high","critical"
    evidence: str


def _severity_from_delta(delta: int) -> str:
    if delta == 0:
        return "none"
    elif delta == 1:
        return "low"
    elif delta <= 5:
        return "high"    # 2-5 unreported calls = high severity (SC3 spec: delta=2 → high)
    else:
        return "critical"


async def check_cross_layer(
    trace_id: str,
    spans: list,
    host_telemetry: list[dict] | None = None,
) -> CrossLayerResult:
    """
    Compare agent-reported network calls vs host-observed connections.
    host_telemetry: list of dicts with 'process_guid' and 'event_type' etc.
    """
    def _get(s, key, default=None):
        return s.get(key, default) if isinstance(s, dict) else getattr(s, key, default)

    # Count agent-reported API/network calls
    agent_calls = sum(
        1 for s in spans
        if _get(s, "action", "") in ("api_call", "network_call", "http_request", "tool_use")
    )

    # Count host-observed network connections for same process_guids
    process_guids = {_get(s, "process_guid") for s in spans if _get(s, "process_guid")}

    host_calls = 0
    if host_telemetry:
        for event in host_telemetry:
            pg = event.get("process_guid")
            etype = event.get("event_type", "")
            if pg in process_guids and etype in ("NetworkConnect", "network_connect", "tcp_connect"):
                host_calls += 1

    delta = host_calls - agent_calls
    severity = _severity_from_delta(abs(delta))

    if delta == 0:
        evidence = f"Agent and host agree: {agent_calls} network calls"
    elif delta > 0:
        evidence = (
            f"Host observed {host_calls} connections but agent only reported {agent_calls} "
            f"(delta={delta}, potential undisclosed activity)"
        )
    else:
        evidence = (
            f"Agent reported {agent_calls} calls but host only saw {host_calls} "
            f"(delta={delta}, potential fabrication)"
        )

    return CrossLayerResult(
        trace_id=trace_id,
        agent_reported_calls=agent_calls,
        host_observed_calls=host_calls,
        delta=delta,
        severity=severity,
        evidence=evidence,
    )


class CrossLayerAgent:
    """POC interface for cross-layer discrepancy analysis."""

    def __init__(self, correlator=None) -> None:
        self._correlator = correlator

    async def check(
        self,
        trace_id: str,
        spans: list,
        host_events: list[dict] | None = None,
    ) -> CrossLayerResult:
        return await check_cross_layer(
            trace_id=trace_id,
            spans=spans,
            host_telemetry=host_events,
        )
