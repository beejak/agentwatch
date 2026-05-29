"""Blast radius calculator — static analysis of what an agent can reach."""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from watchtower.access_graph.manifest import AgentManifest


def calculate_blast_radius(manifest: "AgentManifest", all_manifests: list["AgentManifest"] | None = None) -> list[str]:
    """
    Calculate the static blast radius for an agent.
    Returns a list of resource/agent identifiers this agent can reach.
    """
    reached: set[str] = set()

    # Direct system access
    for sys in manifest.allowed_systems:
        reached.add(sys)

    # Data categories
    for cat in manifest.data_access:
        reached.add(cat)

    # Agents this agent can call
    for callee in manifest.allowed_callees:
        reached.add(callee)

    # If we have all manifests, do one-hop expansion through callees
    if all_manifests:
        callee_set = set(manifest.allowed_callees)
        for m in all_manifests:
            if m.agent_id in callee_set:
                for sys in m.allowed_systems:
                    reached.add(sys)
                for callee2 in m.allowed_callees:
                    reached.add(callee2)

    return sorted(reached)
