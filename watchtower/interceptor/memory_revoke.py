"""Memory access revocation — prevents agents from writing to memory."""
from __future__ import annotations

import asyncio


class MemoryRevoker:
    """Tracks agents whose memory write access has been revoked."""

    def __init__(self) -> None:
        self._revoked: set[str] = set()
        self._lock = asyncio.Lock()

    async def revoke_write(self, agent_id: str) -> None:
        async with self._lock:
            self._revoked.add(agent_id)

    async def is_write_revoked(self, agent_id: str) -> bool:
        async with self._lock:
            return agent_id in self._revoked

    async def restore_write(self, agent_id: str) -> None:
        async with self._lock:
            self._revoked.discard(agent_id)

    async def get_all_revoked(self) -> list[str]:
        async with self._lock:
            return list(self._revoked)
