# SKILL: Layer 13 — Interceptor

## Job
Act when something is wrong. Halt, throttle, quarantine, revoke trust.
Blast radius query on activation. Revoke memory write access.
NEVER act silently. Every action logged to Chronicle.

## Files to create
- watchtower/interceptor/interceptor.py   — main interceptor
- watchtower/interceptor/quarantine.py    — quarantine registry
- watchtower/interceptor/memory_revoke.py — memory access revocation

## InterceptorAction model
```python
class InterceptorAction(BaseModel):
    action_id:       str
    trigger:         str    # "analyst","policy_engine","mim","access_graph"
    target_agent:    str
    action_type:     str    # "halt","throttle","quarantine","revoke_memory","revoke_trust"
    blast_radius:    list[str]  # all agents quarantined
    reason:          str
    timestamp:       float
    logged:          bool = True  # must always be True
```

## Interceptor interface
```python
class Interceptor:
    async def halt(self, agent_id: str, reason: str, trigger: str) -> InterceptorAction: ...
    async def quarantine(self, agent_id: str, reason: str, trigger: str) -> InterceptorAction: ...
    async def revoke_memory_write(self, agent_id: str, reason: str) -> InterceptorAction: ...
    async def is_quarantined(self, agent_id: str) -> bool: ...
    async def get_blast_radius(self, agent_id: str) -> list[str]: ...
```

## Rules
- On activation: query Access Graph for blast_radius immediately
- Quarantine the agent + all agents in blast_radius
- Every action written to Chronicle as interceptor_acts event
- Never raise exceptions — return InterceptorAction always
- logged=True must be set AFTER Chronicle write confirms

## Gate requirements (gate_13_interceptor.py)
- halt() halts target and writes to Chronicle
- quarantine() returns blast_radius from Access Graph
- revoke_memory_write() prevents subsequent MIM writes
- is_quarantined() returns True after quarantine
- Every InterceptorAction appears in Chronicle (verify via reader)
- Interceptor never acts silently (logged=True always)
