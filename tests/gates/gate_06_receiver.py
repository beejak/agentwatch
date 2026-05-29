"""Gate 06: Receiver — HMAC verification and signal processing."""
import json
import time
import uuid
import pytest

from watchtower.core.signal import Signal
from watchtower.receiver.verification import SignalVerifier
from watchtower.receiver.receiver import SignalReceiver

SECRET = "test-secret-key"


@pytest.fixture
def verifier():
    return SignalVerifier()


@pytest.fixture
def make_signal():
    def _make(**kwargs):
        return Signal(
            trace_id=kwargs.get("trace_id", str(uuid.uuid4())),
            span_id=str(uuid.uuid4()),
            agent_id=kwargs.get("agent_id", "test-agent"),
            action=kwargs.get("action", "llm_call"),
            status="ok",
            timestamp=time.time(),
            duration_ms=100.0,
            tokens_in=50,
            tokens_out=25,
            summary="test",
        )
    return _make


@pytest.fixture
def receiver():
    return SignalReceiver(secret=SECRET)


async def test_sign_and_verify(verifier, make_signal):
    signal = make_signal()
    hmac_val = await verifier.sign(signal, SECRET)
    assert await verifier.verify(signal, hmac_val, SECRET) is True


async def test_wrong_hmac_rejected(verifier, make_signal):
    signal = make_signal()
    assert await verifier.verify(signal, "wrong_hmac_value", SECRET) is False


async def test_tampered_signal_rejected(verifier, make_signal):
    """Field modified after signing should fail verification."""
    signal = make_signal()
    hmac_val = await verifier.sign(signal, SECRET)
    # Tamper the signal
    signal.tokens_in = 9999
    assert await verifier.verify(signal, hmac_val, SECRET) is False


async def test_valid_signal_accepted(receiver, verifier, make_signal):
    signal = make_signal()
    hmac_val = await verifier.sign(signal, SECRET)
    entry = {"signal": signal.model_dump_json(), "hmac": hmac_val}
    result = await receiver.process_entry(entry)
    assert result is True
    assert len(receiver._verified_signals) == 1


async def test_invalid_signal_dropped(receiver, make_signal):
    signal = make_signal()
    entry = {"signal": signal.model_dump_json(), "hmac": "bad_hmac"}
    result = await receiver.process_entry(entry)
    assert result is False
    assert len(receiver._verified_signals) == 0


async def test_rejection_logged(receiver, make_signal):
    signal = make_signal()
    entry = {"signal": signal.model_dump_json(), "hmac": "bad_hmac"}
    await receiver.process_entry(entry)
    assert len(receiver._rejected_entries) > 0


async def test_throughput_10_per_second(receiver, verifier, make_signal):
    """Receiver must process at least 10 signals per second."""
    N = 20
    entries = []
    for _ in range(N):
        signal = make_signal()
        hmac_val = await verifier.sign(signal, SECRET)
        entries.append({"signal": signal.model_dump_json(), "hmac": hmac_val})

    start = time.time()
    for entry in entries:
        await receiver.process_entry(entry)
    elapsed = time.time() - start

    rate = N / elapsed if elapsed > 0 else float("inf")
    assert rate >= 10, f"Throughput {rate:.1f} signals/s < 10 signals/s"
    assert len(receiver._verified_signals) == N
