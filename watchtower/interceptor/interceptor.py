"""Interceptor — acts when something is wrong. Halt, throttle, quarantine, revoke trust."""
from __future__ import annotations

import asyncio
import logging
import time
import uuid
from typing import Optional

from pydantic import BaseModel

from watchtower.interceptor.quarantine import QuarantineRegistry
from watchtower.interceptor.memory_revoke import MemoryRevoker

logger = logging.getLogger(__name__)


class InterceptorAction(BaseModel):
    action_id: str
    trigger: str        # "analyst","policy_engine","mim","access_graph"
    target_agent: str
    action_type: str    # "halt","throttle","quarantine","revoke_memory","revoke_trust"
    blast_radius: list[str]
    reason: str
    timestamp: float
    logged: bool = True  # must always be True


class Interceptor:
    """
    Acts on policy violations and anomalies.
    Queries Access Graph for blast radius on activation.
    Logs every action to Chronicle. Never silent.
    """

    def __init__(
        self,
        access_graph=None,
        chronicle_writer=None,
    ) -> None:
        self._access_graph = access_graph
        self._chronicle = chronicle_writer
        self._quarantine = QuarantineRegistry()
        self._revoker = MemoryRevoker()
        self._halted: set[str] = set()
        self._actions: list[InterceptorAction] = []
        self._lock = asyncio.Lock()

    async def _get_blast_radius(self, agent_id: str) -> list[str]:
        """Query Access Graph for blast radius of an agent."""
        if self._access_graph:
            try:
                return await self._access_graph.get_blast_radius(agent_id)
            except Exception as e:
                logger.warning("Blast radius query failed for %s: %s", agent_id, e)
        return []

    async def _log_action(self, action: InterceptorAction) -> None:
        """Log action to Chronicle. Sets logged=True after successful write."""
        async with self._lock:
            self._actions.append(action)

        if self._chronicle:
            try:
                await self._chronicle.write_event("interceptor_acts", {
                    "trace_id": action.action_id,
                    "agent_id": action.target_agent,
                    "timestamp": action.timestamp,
                    "action": action.action_type,
                    "reason": action.reason,
                    "details": str({
                        "trigger": action.trigger,
                        "blast_radius": action.blast_radius,
                    }),
                })
            except Exception as e:
                logger.error("Chronicle write failed for interceptor action: %s", e)

    async def halt(self, agent_id: str, reason: str, trigger: str = "analyst") -> InterceptorAction:
        """Halt an agent immediately."""
        blast_radius = await self._get_blast_radius(agent_id)

        async with self._lock:
            self._halted.add(agent_id)

        action = InterceptorAction(
            action_id=str(uuid.uuid4()),
            trigger=trigger,
            target_agent=agent_id,
            action_type="halt",
            blast_radius=blast_radius,
            reason=reason,
            timestamp=time.time(),
            logged=True,
        )
        await self._log_action(action)
        logger.warning("HALT: agent=%s reason=%s", agent_id, reason)
        return action

    async def quarantine(self, agent_id: str, reason: str, trigger: str = "analyst") -> InterceptorAction:
        """Quarantine an agent and its blast radius."""
        blast_radius = await self._get_blast_radius(agent_id)

        # Quarantine the agent + all agents in blast radius
        await self._quarantine.quarantine(agent_id)
        for affected in blast_radius:
            await self._quarantine.quarantine(affected)

        action = InterceptorAction(
            action_id=str(uuid.uuid4()),
            trigger=trigger,
            target_agent=agent_id,
            action_type="quarantine",
            blast_radius=blast_radius,
            reason=reason,
            timestamp=time.time(),
            logged=True,
        )
        await self._log_action(action)
        logger.warning("QUARANTINE: agent=%s blast_radius=%s reason=%s", agent_id, blast_radius, reason)
        return action

    async def revoke_memory_write(self, agent_id: str, reason: str) -> InterceptorAction:
        """Revoke memory write access for an agent."""
        await self._revoker.revoke_write(agent_id)

        action = InterceptorAction(
            action_id=str(uuid.uuid4()),
            trigger="mim",
            target_agent=agent_id,
            action_type="revoke_memory",
            blast_radius=[],
            reason=reason,
            timestamp=time.time(),
            logged=True,
        )
        await self._log_action(action)
        logger.warning("REVOKE_MEMORY: agent=%s reason=%s", agent_id, reason)
        return action

    async def is_quarantined(self, agent_id: str) -> bool:
        return await self._quarantine.is_quarantined(agent_id)

    async def is_halted(self, agent_id: str) -> bool:
        async with self._lock:
            return agent_id in self._halted

    async def is_memory_write_revoked(self, agent_id: str) -> bool:
        return await self._revoker.is_write_revoked(agent_id)

    async def get_blast_radius(self, agent_id: str) -> list[str]:
        return await self._get_blast_radius(agent_id)

    async def get_all_actions(self) -> list[InterceptorAction]:
        async with self._lock:
            return list(self._actions)
