"""Unit tests for the SignalEmitter SDK (no ClickHouse — fake writer captures signals)."""
import pytest

from watchtower.emitter import SignalEmitter
from watchtower.receiver.verification import SignalVerifier


class _FakeWriter:
    def __init__(self):
        self.signals = []
    async def write_signal(self, s):
        self.signals.append(s)
    async def flush(self):
        pass
    async def stop(self):
        pass


async def _emitter():
    return await SignalEmitter("orchestrator", chronicle_writer=_FakeWriter(), secret="k").start()


async def test_emit_builds_and_sends_signal():
    em = await _emitter()
    sig = await em.emit("delegate", trace_id="t1", summary="plan")
    assert sig.agent_id == "orchestrator" and sig.action == "delegate" and sig.trace_id == "t1"
    assert em._writer.signals[-1] is sig


async def test_agent_override_and_parent_chain():
    em = await _emitter()
    root = await em.emit("delegate", trace_id="t")
    child = await em.emit("tool_use", trace_id="t", agent_id="worker-b",
                          parent_span_id=root.span_id, status="error")
    assert child.agent_id == "worker-b"           # per-emit agent override
    assert child.parent_span_id == root.span_id    # call-tree chaining
    assert child.status == "error"


async def test_span_context_manager_records_duration_and_status():
    em = await _emitter()
    async with em.span("work", trace_id="t") as s:
        s["status"] = "error"
        s["summary"] = "boom"
    emitted = em._writer.signals[-1]
    assert emitted.action == "work" and emitted.status == "error"
    assert emitted.summary == "boom" and emitted.duration_ms >= 0.0


async def test_emitted_signal_is_hmac_verifiable():
    em = await SignalEmitter("a", chronicle_writer=_FakeWriter(), secret="sekret").start()
    sig = await em.emit("x", trace_id="t")
    v = SignalVerifier()
    h = await v.sign(sig, "sekret")
    assert await v.verify(sig, h, "sekret")
    assert not await v.verify(sig, h, "wrong-secret")
