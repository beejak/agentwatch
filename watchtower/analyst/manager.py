"""Analyst Manager — orchestrates sub-agents for trace analysis."""
from __future__ import annotations

from typing import Any, Optional

from watchtower.analyst.attribution import AttributionResult, attribute_failure
from watchtower.analyst.silent import SilentFailureResult, detect_silent_failure
from watchtower.analyst.cross import CrossLayerResult, check_cross_layer


class AnalystManager:
    """
    Orchestrates attribution, silent failure, and cross-layer analysis.
    Accepts spans directly (Chronicle reader can be injected for production).
    """

    def __init__(self, chronicle_reader=None) -> None:
        self._reader = chronicle_reader
        # In-memory span store for testing
        self._trace_spans: dict[str, list] = {}
        self._host_telemetry: dict[str, list[dict]] = {}

    def load_spans(self, trace_id: str, spans: list) -> None:
        """Load spans for a trace (for testing without Chronicle)."""
        self._trace_spans[trace_id] = spans

    def load_host_telemetry(self, trace_id: str, events: list[dict]) -> None:
        """Load host telemetry events for a trace."""
        self._host_telemetry[trace_id] = events

    async def _get_spans(self, trace_id: str) -> list:
        spans = self._trace_spans.get(trace_id, [])
        if not spans and self._reader:
            rows = await self._reader.get_trace(trace_id)
            # Convert dicts to simple objects if needed
            return rows
        return spans

    async def attribute_failure(self, trace_id: str) -> AttributionResult:
        """SC1: Attribute a coordination failure to the specific agent."""
        spans = await self._get_spans(trace_id)
        return await attribute_failure(trace_id, spans)

    async def detect_silent_failure(self, trace_id: str) -> SilentFailureResult:
        """SC2: Detect silent failure patterns (loops, token burn)."""
        spans = await self._get_spans(trace_id)
        return await detect_silent_failure(trace_id, spans)

    async def check_cross_layer(self, trace_id: str) -> CrossLayerResult:
        """SC3: Check for discrepancies between agent reports and host telemetry."""
        spans = await self._get_spans(trace_id)
        host_telemetry = self._host_telemetry.get(trace_id, [])
        return await check_cross_layer(trace_id, spans, host_telemetry)

    async def full_report(self, trace_id: str) -> dict:
        """Run all three analyses and return combined report."""
        attribution = await self.attribute_failure(trace_id)
        silent = await self.detect_silent_failure(trace_id)
        cross = await self.check_cross_layer(trace_id)

        return {
            "trace_id": trace_id,
            "attribution": attribution.model_dump(),
            "silent_failure": silent.model_dump(),
            "cross_layer": cross.model_dump(),
        }
