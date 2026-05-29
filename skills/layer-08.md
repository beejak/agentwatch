# SKILL: Layer 08 — Chronicle

## Job
Append-only ClickHouse writer + reader.
All event streams in one place. Nothing deleted. Nothing updated.

## Files to create
- watchtower/chronicle/writer.py    — async batch writer
- watchtower/chronicle/schema.sql   — CREATE TABLE statements
- watchtower/chronicle/reader.py    — query interface for Analyst

## Tables (all append-only, MergeTree, 90-day TTL)
- agent_spans         — Signal events from agents
- host_telemetry      — Sysmon/Falco OS-level events
- memory_events       — MIM read/write events
- content_results     — Content inspection flags
- policy_decisions    — Policy engine decisions
- verdicts            — Verdict records (all 5 sources)
- interceptor_acts    — Interceptor actions
- discovery_events    — Discovery scan events

## Writer interface
```python
class ChronicleWriter:
    async def write_signal(self, signal: Signal) -> None: ...
    async def write_event(self, event_type: str, payload: dict) -> None: ...
    async def flush(self) -> None:
        """Force flush batch immediately. Call before test assertions."""
        ...
```
- Batch: accumulate 100 events OR 1 second, whichever first
- Fire-and-forget from caller perspective
- writer.flush() must be awaitable for tests

## Reader interface  
```python
class ChronicleReader:
    async def get_trace(self, trace_id: str) -> list[dict]: ...
    async def get_agent_verdicts(self, agent_id: str, limit: int = 50) -> list[dict]: ...
    async def get_silent_failures(self, hours: int = 24) -> list[dict]: ...
    async def get_event_stream(self, event_type: str, since: float) -> list[dict]: ...
```

## CRITICAL constraints
- No UPDATE statements anywhere in schema.sql
- No DELETE statements anywhere in schema.sql  
- ENGINE = MergeTree() on all tables (not ReplacingMergeTree)
- All tables have: PARTITION BY toDate(timestamp) TTL toDate(timestamp) + INTERVAL 90 DAY
- timestamp column: DateTime64(3, 'UTC')

## Gate requirements (gate_08_chronicle.py)
- Signal written → appears in get_trace() after flush()
- Schema has no UPDATE or DELETE in schema.sql
- All 8 event stream tables accept correct payload
- Reader returns events in timestamp ascending order
- TTL clause present in all CREATE TABLE statements
- writer.flush() works correctly before assertions
