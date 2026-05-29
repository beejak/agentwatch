"""TelemetryCorrelator — maps process_guid to trace_id for cross-layer analysis."""
from __future__ import annotations

import asyncio
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from watchtower.host_telemetry.sysmon import SysmonEvent


class TelemetryCorrelator:
    """
    In-memory correlator mapping process_guid → trace_id.
    Called at agent startup to register the mapping.
    """

    def __init__(self) -> None:
        self._pg_to_trace: dict[str, str] = {}
        self._trace_to_events: dict[str, list] = {}
        self._lock = asyncio.Lock()

    async def register(self, process_guid: str, trace_id: str) -> None:
        """Map a process_guid to a trace_id at agent startup."""
        async with self._lock:
            self._pg_to_trace[process_guid] = trace_id

    async def resolve(self, process_guid: str) -> Optional[str]:
        """Return trace_id for a process_guid, or None if not registered."""
        async with self._lock:
            return self._pg_to_trace.get(process_guid)

    async def ingest_event(self, event) -> None:
        """Ingest a SysmonEvent, correlating it to a trace_id."""
        async with self._lock:
            trace_id = self._pg_to_trace.get(event.process_guid)
            if trace_id:
                event = event.model_copy(update={"trace_id": trace_id})
                events = self._trace_to_events.setdefault(trace_id, [])
                events.append(event)

    async def get_events_for_trace(self, trace_id: str) -> list:
        """Return all SysmonEvents correlated to a trace_id."""
        async with self._lock:
            return list(self._trace_to_events.get(trace_id, []))
