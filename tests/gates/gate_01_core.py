"""Gate 01: Core primitives — Signal, Trace, Span, EventType."""
import pytest
import uuid
import time
import hashlib



def test_signal_import():
    from watchtower.core.signal import Signal
    assert Signal is not None


def test_signal_create_basic(make_signal):
    sig = make_signal()
    assert sig.trace_id
    assert sig.span_id
    assert sig.agent_id == "agent-a"
    assert sig.action == "llm_call"
    assert sig.status == "ok"


def test_signal_all_fields_present(make_signal):
    sig = make_signal()
    required = [
        "trace_id", "span_id", "parent_span_id", "agent_id", "action",
        "status", "timestamp", "duration_ms", "tokens_in", "tokens_out",
        "model", "cost", "instruction_hash", "caller_agent_id",
        "process_guid", "retrieval_flag", "memory_op", "framework_fault",
        "policy_checked", "summary"
    ]
    for field in required:
        assert hasattr(sig, field), f"Missing field: {field}"


def test_signal_serialise_roundtrip(make_signal):
    sig = make_signal(agent_id="test-agent", action="tool_use")
    d = sig.model_dump()
    from watchtower.core.signal import Signal
    sig2 = Signal(**d)
    assert sig2.trace_id == sig.trace_id
    assert sig2.agent_id == sig.agent_id
    assert sig2.action == sig.action


def test_signal_instruction_hash():
    from watchtower.core.signal import Signal
    sig = Signal(
        trace_id=str(uuid.uuid4()),
        span_id=str(uuid.uuid4()),
        agent_id="test",
        action="handoff",
        status="ok",
        timestamp=time.time(),
        summary="test"
    )
    instruction = "delegate task X to worker"
    h = sig.compute_instruction_hash(instruction)
    expected = hashlib.sha256(instruction.encode()).hexdigest()
    assert h == expected


def test_signal_factory_method():
    from watchtower.core.signal import Signal
    sig = Signal.create(agent_id="orchestrator", action="delegate")
    assert sig.agent_id == "orchestrator"
    assert sig.action == "delegate"
    assert sig.trace_id
    assert sig.span_id


def test_event_type_enum():
    from watchtower.core.events import EventType
    assert hasattr(EventType, "AGENT_SPAN")
    assert hasattr(EventType, "HOST_TELEMETRY")
    assert hasattr(EventType, "MEMORY_EVENT")
    assert hasattr(EventType, "CONTENT_RESULT")
    assert hasattr(EventType, "POLICY_DECISION")
    assert hasattr(EventType, "VERDICT")
    assert hasattr(EventType, "INTERCEPTOR_ACTION")
    assert hasattr(EventType, "DISCOVERY_EVENT")


def test_trace_and_span():
    from watchtower.core.trace import Trace, Span
    trace = Trace(trace_id=str(uuid.uuid4()))
    span = Span(
        trace_id=trace.trace_id,
        span_id=str(uuid.uuid4()),
        agent_id="test",
        action="llm_call"
    )
    assert span.trace_id == trace.trace_id
