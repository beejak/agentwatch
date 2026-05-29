"""Quarantine registry — tracks quarantined agents."""
from __future__ import annotations

import asyncio


class QuarantineRegistry:
    """In-memory quarantine registry."""

    def __init__(self) -> None:
        self._quarantined: set[str] = set()
        self._lock = asyncio.Lock()

    async def quarantine(self, agent_id: str) -> None:
        async with self._lock:
            self._quarantined.add(agent_id)

    async def is_quarantined(self, agent_id: str) -> bool:
        async with self._lock:
            return agent_id in self._quarantined

    async def get_all(self) -> list[str]:
        async with self._lock:
            return list(self._quarantined)

    async def release(self, agent_id: str) -> None:
        async with self._lock:
            self._quarantined.discard(agent_id)
