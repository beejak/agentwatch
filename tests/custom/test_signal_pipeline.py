"""Custom tests — signal pipeline integrity (emit → receive → verify)."""
from __future__ import annotations

import hashlib
import hmac
import json
import uuid

import pytest

from watchtower.core.signal import Signal
from watchtower.receiver.receiver import SignalReceiver
from watchtower.receiver.verification import SignalVerifier


SECRET = "pipeline-test-secret"


def _make_signal(agent_id="pipeline-agent") -> Signal:
    return Signal(
        trace_id=str(uuid.uuid4()),
        agent_id=agent_id,
        action="llm_call",
        summary="pipeline test",
    )


def _emit_payload(signal: Signal, secret: str) -> dict:
    """Mimics orchestrator.emit — produces the xadd field dict."""
    signal_json = json.dumps(signal.model_dump(), sort_keys=True, default=str)
    sig = hmac.new(secret.encode(), signal_json.encode(), hashlib.sha256).hexdigest()
    return {"signal": signal_json, "hmac": sig}


@pytest.mark.asyncio
async def test_emit_format_verifies():
    """Stream entry produced by emit is accepted by receiver."""
    verifier = SignalVerifier()
    signal = _make_signal()
    entry = _emit_payload(signal, SECRET)

    receiver = SignalReceiver(secret=SECRET, verifier=verifier)
    accepted = await receiver.process_entry(entry)
    assert accepted


@pytest.mark.asyncio
async def test_emit_with_wrong_secret_rejected():
    verifier = SignalVerifier()
    signal = _make_signal()
    entry = _emit_payload(signal, "wrong-secret")

    receiver = SignalReceiver(secret=SECRET, verifier=verifier)
    accepted = await receiver.process_entry(entry)
    assert not accepted


@pytest.mark.asyncio
async def test_missing_hmac_field_rejected():
    signal = _make_signal()
    entry = {"signal": json.dumps(signal.model_dump(), default=str)}
    # No "hmac" field
    receiver = SignalReceiver(secret=SECRET)
    accepted = await receiver.process_entry(entry)
    assert not accepted


@pytest.mark.asyncio
async def test_missing_signal_field_rejected():
    entry = {"hmac": "abc"}
    receiver = SignalReceiver(secret=SECRET)
    accepted = await receiver.process_entry(entry)
    assert not accepted


@pytest.mark.asyncio
async def test_corrupt_json_rejected():
    entry = {"signal": "{bad json}", "hmac": "anything"}
    receiver = SignalReceiver(secret=SECRET)
    accepted = await receiver.process_entry(entry)
    assert not accepted


@pytest.mark.asyncio
async def test_signal_roundtrip_preserves_fields():
    """Fields survive Signal → JSON → Signal reconstruction."""
    original = Signal(
        trace_id="trace-123",
        agent_id="agent-abc",
        action="handoff",
        summary="passing control to sub-agent",
        cost=0.0042,
        tokens_in=300,
        tokens_out=150,
    )
    entry = _emit_payload(original, SECRET)
    receiver = SignalReceiver(secret=SECRET)
    await receiver.process_entry(entry)

    assert len(receiver._verified_signals) == 1
    recovered = receiver._verified_signals[0]
    assert recovered.trace_id == "trace-123"
    assert recovered.agent_id == "agent-abc"
    assert recovered.action == "handoff"
    assert abs(recovered.cost - 0.0042) < 1e-9


@pytest.mark.asyncio
async def test_10_signals_all_verified():
    receiver = SignalReceiver(secret=SECRET)
    for _ in range(10):
        signal = _make_signal()
        entry = _emit_payload(signal, SECRET)
        await receiver.process_entry(entry)
    assert len(receiver._verified_signals) == 10
    assert len(receiver._rejected_entries) == 0


@pytest.mark.asyncio
async def test_rejected_signals_logged():
    receiver = SignalReceiver(secret=SECRET)
    for _ in range(3):
        signal = _make_signal()
        entry = _emit_payload(signal, "wrong")
        await receiver.process_entry(entry)
    assert len(receiver._rejected_entries) == 3
    assert len(receiver._verified_signals) == 0
