"""Custom tests — Chronicle writer correctness (no infra required)."""
from __future__ import annotations

import asyncio
import uuid

import pytest

from watchtower.chronicle.writer import ChronicleWriter
from watchtower.core.signal import Signal


def _signal(**kwargs) -> Signal:
    return Signal(
        trace_id=str(uuid.uuid4()),
        agent_id=kwargs.get("agent_id", "agent-a"),
        action=kwargs.get("action", "llm_call"),
        summary=kwargs.get("summary", "test"),
        cost=kwargs.get("cost", 0.001),
    )


@pytest.mark.asyncio
async def test_write_signal_batches_without_client():
    writer = ChronicleWriter(client=None)
    s = _signal()
    await writer.write_signal(s)
    async with writer._lock:
        assert len(writer._batch) == 1


@pytest.mark.asyncio
async def test_flush_clears_batch_when_no_client():
    writer = ChronicleWriter(client=None)
    for _ in range(5):
        await writer.write_signal(_signal())
    await writer.flush()
    async with writer._lock:
        assert len(writer._batch) == 0


@pytest.mark.asyncio
async def test_write_event_batches():
    writer = ChronicleWriter(client=None)
    await writer.write_event("verdicts", {
        "trace_id": str(uuid.uuid4()),
        "agent_id": "agent-x",
        "verdict": "bad",
        "confidence": 0.9,
        "sources": "deterministic",
        "reason": "cost exceeded",
    })
    async with writer._lock:
        assert len(writer._batch) == 1


@pytest.mark.asyncio
async def test_batch_preserved_on_write_error():
    """Batch must not be lost if ClickHouse write fails."""
    class FailingClient:
        def insert(self, *a, **kw):
            raise RuntimeError("ClickHouse down")
        def command(self, *a, **kw):
            pass

    writer = ChronicleWriter(client=FailingClient())
    for _ in range(3):
        await writer.write_signal(_signal())

    await writer.flush()
    # Items should be preserved in batch after failure
    async with writer._lock:
        assert len(writer._batch) == 3


@pytest.mark.asyncio
async def test_generic_cols_match_row_length():
    writer = ChronicleWriter(client=None)
    for et in writer.TABLE_MAP:
        if et == "agent_spans":
            continue
        cols = writer._generic_cols(et)
        payload = {
            "trace_id": "t", "agent_id": "a", "timestamp": 1.0,
            "details": {}, "verdict": "bad", "confidence": 0.9,
            "sources": "det", "reason": "x", "action": "halt",
            "permitted": True, "operation": "write", "content_hash": "abc",
            "flagged": True, "pattern": "minja", "severity": "high",
            "session_id": "s1", "pattern_matched": "inject",
            "event_type": "network", "process_guid": "pg",
            "namespace": "default",
        }
        row = writer._generic_to_row(payload, et)
        assert len(row) == len(cols), f"{et}: row len {len(row)} != cols len {len(cols)}"


@pytest.mark.asyncio
async def test_append_only_no_update():
    """Chronicle writer must never expose UPDATE or DELETE methods."""
    writer = ChronicleWriter(client=None)
    assert not hasattr(writer, "update")
    assert not hasattr(writer, "delete")
    assert not hasattr(writer, "update_signal")
    assert not hasattr(writer, "delete_signal")
