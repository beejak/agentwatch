# SKILL: Layer 16 — Host Telemetry Stub

## Job
Consume Sysmon (Windows) and Falco (Linux) events.
Correlate process_guid → trace_id.
Feed Chronicle host_telemetry table.
This is a STUB — reads from files, not live OS events.

## Files to create
- watchtower/host_telemetry/sysmon.py    — Sysmon XML event parser
- watchtower/host_telemetry/falco.py     — Falco JSON event parser
- watchtower/host_telemetry/correlator.py — process_guid→trace_id mapping

## SysmonEvent model
```python
class SysmonEvent(BaseModel):
    event_id:       int      # Sysmon event ID (1=process, 3=network, 11=file)
    process_guid:   str      # correlation key
    trace_id:       Optional[str]  # populated by Correlator
    event_type:     str      # "process_create","network_connect","file_create"
    details:        dict     # event-specific fields
    timestamp:      float
```

## Correlator interface
```python
class TelemetryCorrelator:
    async def register(self, process_guid: str, trace_id: str) -> None:
        """Called at agent startup to map process to trace."""
        ...
    async def resolve(self, process_guid: str) -> Optional[str]: ...
    async def get_events_for_trace(self, trace_id: str) -> list[SysmonEvent]: ...
```

## Stub behaviour
- Reads from data/sysmon/*.xml files
- Reads from data/falco/*.json files
- Correlator uses in-memory dict for POC
- Feeds to Chronicle host_telemetry table via ChronicleWriter

## Gate requirements (gate_16_telemetry.py)
- Sysmon XML file parsed → SysmonEvent objects
- Correlator maps process_guid → trace_id correctly
- Correlated events appear in Chronicle host_telemetry
- get_events_for_trace() returns correct events for SC3
