"""AccessGraph — in-memory (dict-backed) permission graph for POC.

Neo4j is available in infra but we keep this layer in-memory to avoid
mandatory Neo4j connectivity in every test environment. The interface
mirrors what a Neo4j-backed version would expose.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from watchtower.access_graph.manifest import AgentManifest
from watchtower.access_graph.blast import calculate_blast_radius

if TYPE_CHECKING:
    pass


class AccessGraph:
    """In-memory access graph (dict-backed) — Neo4j-compatible interface."""

    def __init__(self) -> None:
        self._manifests: dict[str, AgentManifest] = {}
        self._lock = asyncio.Lock()

    async def load_manifest(self, manifest: AgentManifest) -> None:
        """Load an agent manifest into the graph."""
        async with self._lock:
            # Compute blast radius if not already set
            if not manifest.blast_radius:
                radius = calculate_blast_radius(
                    manifest,
                    list(self._manifests.values()),
                )
                manifest = manifest.model_copy(update={"blast_radius": radius})
            self._manifests[manifest.agent_id] = manifest

    async def check_action(self, agent_id: str, action: str) -> bool:
        """Return True if the agent is allowed to perform this action."""
        async with self._lock:
            manifest = self._manifests.get(agent_id)
        if manifest is None:
            return False
        return action in manifest.allowed_actions

    async def check_caller(self, caller_id: str, callee_id: str) -> bool:
        """Return True if caller is allowed to call callee (trust matrix)."""
        async with self._lock:
            callee_manifest = self._manifests.get(callee_id)
            caller_manifest = self._manifests.get(caller_id)
        if callee_manifest is None:
            return False
        # Callee must list caller in allowed_callers
        if caller_id in callee_manifest.allowed_callers:
            return True
        # Caller must list callee in allowed_callees
        if caller_manifest and callee_id in caller_manifest.allowed_callees:
            return True
        return False

    async def get_blast_radius(self, agent_id: str) -> list[str]:
        """Return pre-calculated blast radius for agent."""
        async with self._lock:
            manifest = self._manifests.get(agent_id)
        if manifest is None:
            return []
        if manifest.blast_radius:
            return list(manifest.blast_radius)
        # Calculate on the fly
        async with self._lock:
            all_manifests = list(self._manifests.values())
        return calculate_blast_radius(manifest, all_manifests)

    async def flag_dormant(self, inactive_days: int = 7) -> list[str]:
        """Flag agents with no recent activity (stub — returns empty for POC)."""
        # In a real implementation this would check last_seen timestamps
        return []
