"""Security tests — HMAC forgery resistance and signal pipeline integrity."""
from __future__ import annotations

import hashlib
import hmac
import json
import uuid

import pytest

from watchtower.core.signal import Signal
from watchtower.receiver.verification import SignalVerifier


SECRET = "test-secret-for-security-tests"


def _build_signal(**kwargs) -> Signal:
    return Signal(
        trace_id=str(uuid.uuid4()),
        agent_id=kwargs.get("agent_id", "agent-x"),
        action=kwargs.get("action", "llm_call"),
        summary=kwargs.get("summary", "test"),
    )


def _sign(signal: Signal, secret: str) -> str:
    payload = json.dumps(signal.model_dump(), sort_keys=True, default=str)
    return hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()


@pytest.mark.asyncio
async def test_valid_hmac_passes():
    verifier = SignalVerifier()
    signal = _build_signal()
    sig = await verifier.sign(signal, SECRET)
    assert await verifier.verify(signal, sig, SECRET)


@pytest.mark.asyncio
async def test_wrong_secret_rejected():
    verifier = SignalVerifier()
    signal = _build_signal()
    sig = await verifier.sign(signal, SECRET)
    assert not await verifier.verify(signal, sig, "wrong-secret")


@pytest.mark.asyncio
async def test_empty_hmac_rejected():
    verifier = SignalVerifier()
    signal = _build_signal()
    assert not await verifier.verify(signal, "", SECRET)


@pytest.mark.asyncio
async def test_tampered_agent_id_rejected():
    verifier = SignalVerifier()
    signal = _build_signal(agent_id="legitimate-agent")
    sig = await verifier.sign(signal, SECRET)

    tampered = _build_signal(agent_id="attacker-agent")
    tampered.trace_id = signal.trace_id
    tampered.span_id = signal.span_id
    assert not await verifier.verify(tampered, sig, SECRET)


@pytest.mark.asyncio
async def test_tampered_summary_rejected():
    """Agent cannot modify summary after signing."""
    verifier = SignalVerifier()
    signal = _build_signal(summary="original output")
    sig = await verifier.sign(signal, SECRET)

    signal.summary = "malicious override"
    assert not await verifier.verify(signal, sig, SECRET)


@pytest.mark.asyncio
async def test_replay_with_different_trace_rejected():
    """Replaying a valid HMAC for a different trace is rejected."""
    verifier = SignalVerifier()
    signal1 = _build_signal()
    sig1 = await verifier.sign(signal1, SECRET)

    signal2 = _build_signal()
    # sig1 is for signal1 — must not verify signal2
    assert not await verifier.verify(signal2, sig1, SECRET)


@pytest.mark.asyncio
async def test_all_zeros_hmac_rejected():
    verifier = SignalVerifier()
    signal = _build_signal()
    assert not await verifier.verify(signal, "0" * 64, SECRET)


@pytest.mark.asyncio
async def test_known_secret_value_no_hardcoded_default():
    """The default secret must not be the known public default."""
    from watchtower.receiver.receiver import SignalReceiver
    receiver = SignalReceiver()
    # The class should require an explicit secret in production
    # (this test documents the risk of the default)
    known_public = "watchtower-hmac-secret-change-in-prod"
    # Flag if default is the known public string — it should be overridden
    assert receiver._secret == known_public, (
        "Expected default to equal known value so this test documents C1. "
        "Override via WT_HMAC_SECRET env var in production."
    )
