"""Event types for all Chronicle event streams."""
from enum import Enum


class EventType(str, Enum):
    AGENT_SPAN        = "agent_spans"
    HOST_TELEMETRY    = "host_telemetry"
    MEMORY_EVENT      = "memory_events"
    CONTENT_RESULT    = "content_results"
    POLICY_DECISION   = "policy_decisions"
    VERDICT           = "verdicts"
    INTERCEPTOR_ACTION = "interceptor_acts"
    DISCOVERY_EVENT   = "discovery_events"
