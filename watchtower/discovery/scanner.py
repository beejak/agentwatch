"""Agent Scanner — active scanner that polls known namespaces."""
from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from watchtower.discovery.registry import AgentRegistry


class AgentScanner:
    def __init__(self, registry: "AgentRegistry", namespaces: list[str] | None = None) -> None:
        self._registry = registry
        self._namespaces = namespaces or []
        # namespace -> set of agent IDs observed in that namespace
        self._namespace_agents: dict[str, set[str]] = {}

    def _inject_test_agent(self, agent_id: str, namespace: str | None = None) -> None:
        """Test helper: inject an agent into a namespace."""
        ns = namespace or (self._namespaces[0] if self._namespaces else "default")
        if ns not in self._namespace_agents:
            self._namespace_agents[ns] = set()
        self._namespace_agents[ns].add(agent_id)

    async def scan(self) -> list[str]:
        """Returns list of discovered agent IDs not yet in registry."""
        unknown: list[str] = []
        for ns in self._namespaces:
            agents = self._namespace_agents.get(ns, set())
            for agent_id in agents:
                if not await self._registry.is_known(agent_id):
                    unknown.append(agent_id)
                    await self._registry.flag_unknown(agent_id)
        return unknown

    async def run_continuous(self, interval_s: float = 30.0) -> None:
        """Continuously scan at given interval."""
        while True:
            await self.scan()
            await asyncio.sleep(interval_s)
