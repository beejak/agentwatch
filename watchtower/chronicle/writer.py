"""Chronicle Writer — async batch writer to ClickHouse. Append-only."""
from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from typing import Any, Optional

from watchtower.core.signal import Signal

logger = logging.getLogger(__name__)

BATCH_SIZE = 100
BATCH_TIMEOUT = 1.0  # seconds


def _ts_to_dt(ts: float) -> datetime:
    return datetime.fromtimestamp(ts, tz=timezone.utc)


class ChronicleWriter:
    """
    Async batch writer to ClickHouse.
    Accumulates events and flushes when batch is full or timeout reached.
    """

    TABLE_MAP = {
        "agent_spans": "watchtower.agent_spans",
        "host_telemetry": "watchtower.host_telemetry",
        "memory_events": "watchtower.memory_events",
        "content_results": "watchtower.content_results",
        "policy_decisions": "watchtower.policy_decisions",
        "verdicts": "watchtower.verdicts",
        "interceptor_acts": "watchtower.interceptor_acts",
        "discovery_events": "watchtower.discovery_events",
    }

    def __init__(self, client=None) -> None:
        self._client = client
        self._batch: list[tuple[str, dict]] = []  # (event_type, payload)
        self._lock = asyncio.Lock()
        self._flush_task: Optional[asyncio.Task] = None
        self._running = False

    async def start(self) -> None:
        self._running = True
        self._flush_task = asyncio.create_task(self._auto_flush_loop())
        # Apply schema
        if self._client:
            await self._apply_schema()

    async def _apply_schema(self) -> None:
        """Apply the schema SQL if tables don't exist."""
        from pathlib import Path
        schema_path = Path(__file__).parent / "schema.sql"
        if not schema_path.exists():
            return
        schema = schema_path.read_text()
        # Split on semicolons and execute each statement
        for stmt in schema.split(";"):
            # Strip comments and whitespace
            lines = [
                line for line in stmt.splitlines()
                if line.strip() and not line.strip().startswith("--")
            ]
            stmt = "\n".join(lines).strip()
            if stmt:
                try:
                    self._client.command(stmt)
                except Exception as e:
                    logger.debug("Schema stmt skipped: %s", e)

    async def stop(self) -> None:
        self._running = False
        if self._flush_task:
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass
        await self.flush()

    async def write_signal(self, signal: Signal) -> None:
        """Write a Signal to the agent_spans table."""
        payload = {
            "trace_id": signal.trace_id,
            "span_id": signal.span_id,
            "parent_span_id": signal.parent_span_id,
            "agent_id": signal.agent_id,
            "action": signal.action,
            "status": signal.status,
            "timestamp": signal.timestamp,
            "duration_ms": signal.duration_ms,
            "tokens_in": signal.tokens_in,
            "tokens_out": signal.tokens_out,
            "model": signal.model,
            "cost": signal.cost,
            "instruction_hash": signal.instruction_hash,
            "caller_agent_id": signal.caller_agent_id,
            "process_guid": signal.process_guid,
            "retrieval_flag": 1 if signal.retrieval_flag else 0,
            "memory_op": signal.memory_op,
            "framework_fault": 1 if signal.framework_fault else 0,
            "policy_checked": 1 if signal.policy_checked else 0,
            "summary": signal.summary,
        }
        async with self._lock:
            self._batch.append(("agent_spans", payload))
            if len(self._batch) >= BATCH_SIZE:
                await self._flush_locked()

    async def write_event(self, event_type: str, payload: dict) -> None:
        """Write a generic event to the appropriate table."""
        async with self._lock:
            self._batch.append((event_type, payload))
            if len(self._batch) >= BATCH_SIZE:
                await self._flush_locked()

    async def flush(self) -> None:
        """Force flush all pending events."""
        async with self._lock:
            await self._flush_locked()

    async def _flush_locked(self) -> None:
        """Must be called with self._lock held."""
        if not self._batch:
            return
        batch = list(self._batch)
        self._batch.clear()

        if not self._client:
            return

        # Group by event type
        by_type: dict[str, list[dict]] = {}
        for et, payload in batch:
            by_type.setdefault(et, []).append(payload)

        for et, payloads in by_type.items():
            table = self.TABLE_MAP.get(et)
            if not table:
                logger.warning("Unknown event type: %s", et)
                continue
            await self._write_rows(table, et, payloads)

    async def _write_rows(self, table: str, event_type: str, payloads: list[dict]) -> None:
        """Write rows to ClickHouse table."""
        try:
            if event_type == "agent_spans":
                rows = [self._signal_to_row(p) for p in payloads]
                cols = [
                    "trace_id", "span_id", "parent_span_id", "agent_id", "action",
                    "status", "timestamp", "duration_ms", "tokens_in", "tokens_out",
                    "model", "cost", "instruction_hash", "caller_agent_id", "process_guid",
                    "retrieval_flag", "memory_op", "framework_fault", "policy_checked", "summary"
                ]
            else:
                rows = [self._generic_to_row(p) for p in payloads]
                cols = self._generic_cols(event_type)

            self._client.insert(table, rows, column_names=cols)
        except Exception as e:
            logger.error("Chronicle write error for %s: %s", table, e)

    def _signal_to_row(self, p: dict) -> list:
        ts = p["timestamp"]
        if isinstance(ts, float):
            ts = _ts_to_dt(ts)
        return [
            p.get("trace_id", ""),
            p.get("span_id", ""),
            p.get("parent_span_id"),
            p.get("agent_id", ""),
            p.get("action", ""),
            p.get("status", "ok"),
            ts,
            p.get("duration_ms", 0.0),
            p.get("tokens_in", 0),
            p.get("tokens_out", 0),
            p.get("model"),
            p.get("cost", 0.0),
            p.get("instruction_hash"),
            p.get("caller_agent_id"),
            p.get("process_guid"),
            p.get("retrieval_flag", 0),
            p.get("memory_op"),
            p.get("framework_fault", 0),
            p.get("policy_checked", 0),
            p.get("summary", ""),
        ]

    def _generic_to_row(self, p: dict) -> list:
        ts = p.get("timestamp", time.time())
        if isinstance(ts, float):
            ts = _ts_to_dt(ts)
        return [
            p.get("trace_id", ""),
            p.get("agent_id", ""),
            ts,
            json.dumps(p.get("details", p)),
        ]

    def _generic_cols(self, event_type: str) -> list[str]:
        base = ["trace_id", "agent_id", "timestamp", "details"]
        extras = {
            "host_telemetry": ["event_type", "process_guid"],
            "memory_events": ["operation", "content_hash", "flagged", "pattern", "severity", "session_id"],
            "content_results": ["content_hash", "flagged", "confidence", "pattern_matched", "severity", "action"],
            "policy_decisions": ["action", "permitted", "reason"],
            "verdicts": ["verdict", "confidence", "sources", "reason"],
            "interceptor_acts": ["action", "reason"],
            "discovery_events": ["flagged", "namespace"],
        }
        # For generic writes, just use the basic columns
        return base

    async def _auto_flush_loop(self) -> None:
        while self._running:
            await asyncio.sleep(BATCH_TIMEOUT)
            await self.flush()
