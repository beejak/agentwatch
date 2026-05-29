"""Chronicle Reader — query interface for Analyst and other consumers."""
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


def _to_dict(row, columns: list[str]) -> dict:
    return {col: val for col, val in zip(columns, row)}


class ChronicleReader:
    def __init__(self, client=None) -> None:
        self._client = client

    async def get_trace(self, trace_id: str) -> list[dict]:
        """Return all spans for a trace, ordered by timestamp ascending."""
        if not self._client:
            return []
        try:
            result = self._client.query(
                "SELECT trace_id, span_id, parent_span_id, agent_id, action, status, "
                "toUnixTimestamp64Milli(timestamp)/1000.0 AS timestamp, duration_ms, "
                "tokens_in, tokens_out, model, cost, summary "
                "FROM watchtower.agent_spans "
                "WHERE trace_id = {trace_id:String} "
                "ORDER BY timestamp ASC",
                parameters={"trace_id": trace_id},
            )
            cols = [
                "trace_id", "span_id", "parent_span_id", "agent_id", "action",
                "status", "timestamp", "duration_ms", "tokens_in", "tokens_out",
                "model", "cost", "summary"
            ]
            return [_to_dict(row, cols) for row in result.result_rows]
        except Exception as e:
            logger.error("get_trace error: %s", e)
            return []

    async def get_agent_verdicts(self, agent_id: str, limit: int = 50) -> list[dict]:
        """Return verdict records for an agent, most recent first."""
        if not self._client:
            return []
        try:
            result = self._client.query(
                "SELECT trace_id, agent_id, "
                "toUnixTimestamp64Milli(timestamp)/1000.0 AS timestamp, "
                "details "
                "FROM watchtower.verdicts "
                "WHERE agent_id = {agent_id:String} "
                "ORDER BY timestamp DESC "
                "LIMIT {limit:Int32}",
                parameters={"agent_id": agent_id, "limit": limit},
            )
            cols = ["trace_id", "agent_id", "timestamp", "details"]
            return [_to_dict(row, cols) for row in result.result_rows]
        except Exception as e:
            logger.error("get_agent_verdicts error: %s", e)
            return []

    async def get_silent_failures(self, hours: int = 24) -> list[dict]:
        """
        Detect silent failures: traces where all spans status=ok but span count
        exceeds 50 (infinite retry loop pattern — SC2).
        """
        if not self._client:
            return []
        try:
            since = time.time() - hours * 3600
            since_dt = datetime.fromtimestamp(since, tz=timezone.utc)
            result = self._client.query(
                "SELECT trace_id, agent_id, "
                "countIf(status = 'ok') AS ok_count, "
                "countIf(status != 'ok') AS non_ok_count, "
                "count() AS total, "
                "any(summary) AS summary, "
                "min(toUnixTimestamp64Milli(timestamp)/1000.0) AS first_ts "
                "FROM watchtower.agent_spans "
                "WHERE timestamp >= {since:DateTime64(3, 'UTC')} "
                "GROUP BY trace_id, agent_id "
                "HAVING total > 50 AND non_ok_count = 0 "
                "ORDER BY total DESC",
                parameters={"since": since_dt},
            )
            cols = ["trace_id", "agent_id", "ok_count", "non_ok_count", "total", "summary", "first_ts"]
            rows = [_to_dict(row, cols) for row in result.result_rows]
            # Shape to match SilentFailureItem
            return [
                {
                    "trace_id": r["trace_id"],
                    "agent_id": r["agent_id"],
                    "status": f"ok x{r['total']} (silent loop)",
                    "summary": r["summary"],
                    "timestamp": r["first_ts"],
                }
                for r in rows
            ]
        except Exception as e:
            logger.error("get_silent_failures error: %s", e)
            return []

    async def get_event_stream(self, event_type: str, since: float) -> list[dict]:
        """Return events of a given type since a timestamp."""
        if not self._client:
            return []

        table_map = {
            "agent_spans": "watchtower.agent_spans",
            "host_telemetry": "watchtower.host_telemetry",
            "memory_events": "watchtower.memory_events",
            "content_results": "watchtower.content_results",
            "policy_decisions": "watchtower.policy_decisions",
            "verdicts": "watchtower.verdicts",
            "interceptor_acts": "watchtower.interceptor_acts",
            "discovery_events": "watchtower.discovery_events",
        }
        table = table_map.get(event_type)
        if not table:
            return []

        try:
            since_dt = datetime.fromtimestamp(since, tz=timezone.utc)
            result = self._client.query(
                f"SELECT trace_id, agent_id, "
                f"toUnixTimestamp64Milli(timestamp)/1000.0 AS timestamp, details "
                f"FROM {table} "
                f"WHERE timestamp >= {{since:DateTime64(3, 'UTC')}} "
                f"ORDER BY timestamp ASC",
                parameters={"since": since_dt},
            )
            cols = ["trace_id", "agent_id", "timestamp", "details"]
            return [_to_dict(row, cols) for row in result.result_rows]
        except Exception as e:
            logger.error("get_event_stream error for %s: %s", event_type, e)
            return []
