"""Memory Integrity Monitor (MIM) — watches agent memory read/write operations."""
from __future__ import annotations

import asyncio
import hashlib
import time
from typing import Optional

from pydantic import BaseModel

from watchtower.memory_monitor.detectors.minja import (
    contains_instruction_like_content,
    is_minja_sequence,
)
from watchtower.memory_monitor.detectors.spyware import (
    escalate_severity,
    is_cross_session_repeat,
)


class MemoryEvent(BaseModel):
    agent_id: str
    operation: str          # "read","write","delete"
    content_hash: str
    content_preview: str    # first 200 chars
    flagged: bool
    pattern: Optional[str]  # "minja","spyware","policy_override","instruction_like"
    severity: str
    timestamp: float
    session_id: str


class MemoryIntegrityMonitor:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        # agent_id -> list of recent events (for MINJA sequence detection)
        self._history: dict[str, list[dict]] = {}
        # content_hash -> set of session_ids where seen
        self._hash_sessions: dict[str, set[str]] = {}
        # flagged content hashes
        self._flagged_hashes: set[str] = set()
        # all events
        self._events: list[MemoryEvent] = []

    def _hash(self, content: str) -> str:
        return hashlib.sha256(content.encode()).hexdigest()

    async def on_write(self, agent_id: str, content: str, session_id: str) -> MemoryEvent:
        content_hash = self._hash(content)
        preview = content[:200]
        flagged = False
        pattern: Optional[str] = None
        severity = "low"

        # Check for instruction-like content
        is_instr, matched = contains_instruction_like_content(content)
        if is_instr:
            flagged = True
            pattern = "policy_override"
            severity = "high"

        async with self._lock:
            # Track sessions for this hash
            sessions = self._hash_sessions.setdefault(content_hash, set())
            sessions.add(session_id)

            # Update agent history
            history = self._history.setdefault(agent_id, [])
            history.append({"operation": "write", "content": content})
            # Keep last 20 events
            if len(history) > 20:
                self._history[agent_id] = history[-20:]
            history = list(self._history[agent_id])

        # Check MINJA sequence
        if is_minja_sequence(history):
            flagged = True
            pattern = "minja"
            severity = "high"

        # Check cross-session repeat (SpAIware)
        async with self._lock:
            is_spyware = flagged and is_cross_session_repeat(
                content_hash, self._flagged_hashes, session_id, self._hash_sessions
            )

        if is_spyware:
            pattern = "spyware"
            severity = escalate_severity(severity)

        async with self._lock:
            if flagged:
                self._flagged_hashes.add(content_hash)

        event = MemoryEvent(
            agent_id=agent_id,
            operation="write",
            content_hash=content_hash,
            content_preview=preview,
            flagged=flagged,
            pattern=pattern,
            severity=severity,
            timestamp=time.time(),
            session_id=session_id,
        )

        async with self._lock:
            self._events.append(event)

        return event

    async def on_read(self, agent_id: str, key: str, session_id: str) -> MemoryEvent:
        content_hash = self._hash(key)
        preview = key[:200]

        async with self._lock:
            history = self._history.setdefault(agent_id, [])
            history.append({"operation": "read", "content": key})
            if len(history) > 20:
                self._history[agent_id] = history[-20:]

        event = MemoryEvent(
            agent_id=agent_id,
            operation="read",
            content_hash=content_hash,
            content_preview=preview,
            flagged=False,
            pattern=None,
            severity="low",
            timestamp=time.time(),
            session_id=session_id,
        )

        async with self._lock:
            self._events.append(event)

        return event

    async def get_cross_session_drift(self, agent_id: str) -> float:
        """
        Returns a drift score (0.0-1.0) for how much an agent's memory
        has changed across sessions (based on flagged cross-session writes).
        """
        async with self._lock:
            agent_events = [e for e in self._events if e.agent_id == agent_id]

        if not agent_events:
            return 0.0

        flagged_count = sum(1 for e in agent_events if e.flagged)
        total = len(agent_events)
        return flagged_count / total
