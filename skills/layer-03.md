# SKILL: Layer 03 — Access Graph

## Job
Map permissions for every agent. Enforce on every action.
Pre-calculate blast radius. Agent-to-agent trust matrix.

## Files to create
- watchtower/access_graph/graph.py      — Neo4j-backed permission graph
- watchtower/access_graph/manifest.py   — AgentManifest Pydantic model
- watchtower/access_graph/blast.py      — static blast radius calculation

## AgentManifest model
```python
class AgentManifest(BaseModel):
    agent_id:          str
    allowed_actions:   list[str]    # ["llm_call","tool_use","handoff"]
    allowed_systems:   list[str]    # ["redis","postgres","clickhouse"]
    allowed_callers:   list[str]    # agent IDs allowed to call this agent
    allowed_callees:   list[str]    # agent IDs this agent can call
    memory_scope:      str          # "read_only","read_write","none"
    data_access:       list[str]    # data categories accessible
    blast_radius:      list[str]    # pre-calculated: what this agent can reach
```

## AccessGraph interface
```python
class AccessGraph:
    async def load_manifest(self, manifest: AgentManifest) -> None: ...
    async def check_action(self, agent_id: str, action: str) -> bool: ...
    async def check_caller(self, caller_id: str, callee_id: str) -> bool: ...
    async def get_blast_radius(self, agent_id: str) -> list[str]: ...
    async def flag_dormant(self, inactive_days: int = 7) -> list[str]: ...
```

## Neo4j schema
- Node: Agent {agent_id, created_at}
- Node: System {system_id}
- Node: DataCategory {name}
- Relationship: CAN_CALL (Agent→Agent) {since}
- Relationship: CAN_ACCESS (Agent→System) {actions: list}

## Gate requirements (gate_03_access.py)
- Manifest loads into Neo4j correctly
- check_action() passes for allowed, fails for disallowed
- check_caller() enforces A→B trust matrix
- get_blast_radius() returns correct affected nodes
- ZT re-verification: same check works on repeated calls
