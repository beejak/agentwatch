# SKILL: Layer 10 — Behavioral Baseline

## Job
Per-agent normal profile from Chronicle history.
Three levels: application, host, memory.
New agent restricted mode (< 50 traces).

## Files to create
- watchtower/baseline/engine.py    — orchestrates baseline
- watchtower/baseline/profile.py   — AgentProfile model
- watchtower/baseline/drift.py     — cross-session drift detection

## AgentProfile model
```python
class AgentProfile(BaseModel):
    agent_id:           str
    trace_count:        int     # number of traces used to build profile
    restricted_mode:    bool    # True if trace_count < 50
    # Application level
    avg_step_count:     float
    std_step_count:     float
    avg_duration_ms:    float
    avg_cost:           float
    avg_tokens_in:      float
    avg_tokens_out:     float
    common_actions:     list[str]    # top 5 actions by frequency
    # Memory level
    avg_write_count:    float
    last_updated:       float
```

## BaselineEngine interface
```python
class BaselineEngine:
    async def build_profile(self, agent_id: str) -> AgentProfile: ...
    async def check_deviation(self, agent_id: str, spans: list[Signal]) -> Optional[str]:
        """Returns deviation description if anomalous, None if normal."""
        ...
    async def is_restricted(self, agent_id: str) -> bool: ...
    async def update_profile(self, agent_id: str, new_spans: list[Signal]) -> None: ...
```

## Deviation thresholds
- step_count > avg + 3*std → anomalous
- cost > avg * 10 → anomalous (possible runaway)
- duration > avg * 5 → anomalous

## Gate requirements (gate_10_baseline.py)
- Profile builds from N historical traces in Chronicle
- Deviation detected when step count exceeds avg + 3*std
- is_restricted() returns True for agent with < 50 traces
- update_profile() updates stats correctly
- check_deviation() returns None for normal trace
