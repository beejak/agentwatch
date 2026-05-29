# SKILL: Layer 07 — Memory Integrity Monitor (MIM)

## Job
Watch all agent memory read/write operations.
Detect MINJA pattern (query-only self-poisoning).
Detect SpAIware pattern (cross-session external planting).
Critical anomalies → Interceptor directly (don't wait for Verdict).

## Files to create
- watchtower/memory_monitor/monitor.py          — main MIM
- watchtower/memory_monitor/detectors/minja.py  — MINJA pattern detector
- watchtower/memory_monitor/detectors/spyware.py — SpAIware detector

## MINJA attack pattern (detect this)
1. Attacker sends query-only interactions (no direct write)
2. Agent processes queries and autonomously writes to memory
3. Written content contains: bridging steps + indication prompts + progressive shortening
4. Final memory entry contains policy-override or instruction-like content

## MemoryEvent model
```python
class MemoryEvent(BaseModel):
    agent_id:       str
    operation:      str     # "read","write","delete"
    content_hash:   str     # hash of written content
    content_preview: str    # first 200 chars
    flagged:        bool
    pattern:        Optional[str]  # "minja","spyware","policy_override","instruction_like"
    severity:       str
    timestamp:      float
    session_id:     str     # for cross-session tracking
```

## MIM interface
```python
class MemoryIntegrityMonitor:
    async def on_write(self, agent_id: str, content: str, session_id: str) -> MemoryEvent: ...
    async def on_read(self, agent_id: str, key: str, session_id: str) -> MemoryEvent: ...
    async def get_cross_session_drift(self, agent_id: str) -> float: ...
```

## Gate requirements (gate_07_mim.py)
- Normal memory write passes without flag
- Content with "ignore previous instructions" → flagged=True, pattern=policy_override
- MINJA sequence (query→query→write with instruction content) → flagged=True, pattern=minja
- Cross-session write of same flagged content → severity escalated
- All MemoryEvents have content_hash populated
