"""AgentManifest — Pydantic model for agent permission declarations."""
from __future__ import annotations

from pydantic import BaseModel


class AgentManifest(BaseModel):
    agent_id: str
    allowed_actions: list[str]    # ["llm_call","tool_use","handoff"]
    allowed_systems: list[str]    # ["redis","postgres","clickhouse"]
    allowed_callers: list[str]    # agent IDs allowed to call this agent
    allowed_callees: list[str]    # agent IDs this agent can call
    memory_scope: str             # "read_only","read_write","none"
    data_access: list[str]        # data categories accessible
    blast_radius: list[str]       # pre-calculated: what this agent can reach
