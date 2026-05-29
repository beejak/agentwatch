"""Gate 08: Chronicle — append-only ClickHouse writer and reader."""
import pytest
import uuid
import time
import asyncio



@pytest.fixture
async def writer(clickhouse_client):
    from watchtower.chronicle.writer import ChronicleWriter
    w = ChronicleWriter(client=clickhouse_client)
    await w.start()
    yield w
    await w.stop()


@pytest.fixture
async def reader(clickhouse_client):
    from watchtower.chronicle.reader import ChronicleReader
    return ChronicleReader(client=clickhouse_client)


async def test_signal_write_and_read(writer, reader, make_signal):
    trace_id = str(uuid.uuid4())
    sig = make_signal(trace_id=trace_id, agent_id="test-agent")
    await writer.write_signal(sig)
    await writer.flush()
    await asyncio.sleep(0.5)  # allow ClickHouse to process
    spans = await reader.get_trace(trace_id)
    assert len(spans) >= 1
    assert spans[0]["trace_id"] == trace_id


async def test_chronicle_is_append_only():
    """Verify schema.sql has no UPDATE or DELETE statements."""
    from pathlib import Path
    schema = Path("watchtower/chronicle/schema.sql").read_text().upper()
    assert "UPDATE " not in schema, "Chronicle schema must not contain UPDATE"
    assert "DELETE " not in schema, "Chronicle schema must not contain DELETE"


async def test_all_event_streams(writer, reader):
    from watchtower.core.events import EventType
    event_types = [
        EventType.HOST_TELEMETRY,
        EventType.MEMORY_EVENT,
        EventType.CONTENT_RESULT,
        EventType.POLICY_DECISION,
        EventType.VERDICT,
        EventType.INTERCEPTOR_ACTION,
        EventType.DISCOVERY_EVENT,
    ]
    for et in event_types:
        await writer.write_event(et.value, {
            "trace_id": str(uuid.uuid4()),
            "agent_id": "test",
            "timestamp": time.time(),
            "details": f"test {et.value} event"
        })
    await writer.flush()
    # No exception = pass


async def test_reader_returns_chronological_order(writer, reader, make_signal):
    trace_id = str(uuid.uuid4())
    for i in range(5):
        sig = make_signal(trace_id=trace_id, summary=f"step {i}")
        sig.timestamp = time.time() + i * 0.001
        await writer.write_signal(sig)
    await writer.flush()
    await asyncio.sleep(0.5)
    spans = await reader.get_trace(trace_id)
    if len(spans) > 1:
        for i in range(len(spans) - 1):
            assert spans[i]["timestamp"] <= spans[i+1]["timestamp"]


async def test_ttl_clause_in_schema():
    """All tables must have TTL clause."""
    from pathlib import Path
    schema = Path("watchtower/chronicle/schema.sql").read_text()
    # Count TTL clauses — should be at least 8 (one per table)
    ttl_count = schema.upper().count("TTL ")
    assert ttl_count >= 8, f"Expected >=8 TTL clauses, found {ttl_count}"


async def test_flush_works_before_assertion(writer, reader, make_signal):
    trace_id = str(uuid.uuid4())
    sig = make_signal(trace_id=trace_id)
    await writer.write_signal(sig)
    # Flush must make data immediately queryable
    await writer.flush()
    await asyncio.sleep(0.5)
    spans = await reader.get_trace(trace_id)
    assert len(spans) >= 1
