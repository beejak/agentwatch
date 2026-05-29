"""Agent Registry — dict-backed for POC."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Optional


class AgentRegistry:
    def __init__(self) -> None:
        self._agents: dict[str, dict] = {}
        self._flagged: list[str] = []
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        pass

    async def stop(self) -> None:
        pass

    async def register(self, agent_id: str, metadata: dict) -> None:
        async with self._lock:
            self._agents[agent_id] = {
                "agent_id": agent_id,
                "metadata": metadata,
                "registered_at": datetime.now(timezone.utc).isoformat(),
            }

    async def is_known(self, agent_id: str) -> bool:
        async with self._lock:
            return agent_id in self._agents

    async def get_all(self) -> list[dict]:
        async with self._lock:
            return list(self._agents.values())

    async def flag_unknown(self, agent_id: str, return_event: bool = False) -> Optional[dict]:
        async with self._lock:
            if agent_id not in self._flagged:
                self._flagged.append(agent_id)
        if return_event:
            event = {
                "agent_id": agent_id,
                "flagged": True,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            return event
        return None

    async def get_flagged(self) -> list[str]:
        async with self._lock:
            return list(self._flagged)
