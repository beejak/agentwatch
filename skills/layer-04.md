# SKILL: Layer 04 — Policy Engine

## Job
Pre-execution verification. Default-deny.
Every proposed action checked before it runs.
Temporal constraints: Before, After, Forall, Exists.

## Files to create
- watchtower/policy_engine/engine.py    — main policy engine
- watchtower/policy_engine/temporal.py  — temporal constraint types

## TemporalConstraint
```python
from enum import Enum
from pydantic import BaseModel

class ConstraintType(Enum):
    BEFORE   = "before"   # A must happen before B
    AFTER    = "after"    # A must happen after B
    FORALL   = "forall"   # condition must hold for all actions
    EXISTS   = "exists"   # condition must hold for at least one action

class TemporalConstraint(BaseModel):
    type:       ConstraintType
    action_a:   str
    action_b:   str
    reason:     str

class PolicyDecision(BaseModel):
    agent_id:   str
    action:     str
    permitted:  bool
    reason:     str
    timestamp:  float
```

## PolicyEngine interface
```python
class PolicyEngine:
    async def check(self, agent_id: str, action: str, context: dict) -> PolicyDecision: ...
    async def add_constraint(self, agent_id: str, constraint: TemporalConstraint) -> None: ...
    async def get_constraints(self, agent_id: str) -> list[TemporalConstraint]: ...
```

## Rules
- Default-deny: if no explicit ALLOW rule, action is denied
- check() must be called BEFORE every agent action
- All decisions logged (return PolicyDecision always, never raise)

## Gate requirements (gate_04_policy.py)
- Permitted action returns PolicyDecision(permitted=True)
- Forbidden action returns PolicyDecision(permitted=False)
- BEFORE(verify, write) constraint: write denied if verify not in trace yet
- AFTER(auth, api_call) constraint: api_call denied before auth
- Every PolicyDecision has reason field populated
