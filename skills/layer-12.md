# SKILL: Layer 12 — Analyst

## Job
Read Chronicle + Verdict + Baseline + Signatures.
Answer the three proof questions (SC1, SC2, SC3).
Sub-agent architecture: Manager + AttributionAgent + SilentAgent + CrossLayerAgent.

## Files to create
- watchtower/analyst/manager.py         — orchestrates sub-agents
- watchtower/analyst/attribution.py     — SC1: coordination failure attribution
- watchtower/analyst/silent.py          — SC2: silent failure detection
- watchtower/analyst/cross.py           — SC3: cross-layer host discrepancy

## AttributionResult (SC1)
```python
class AttributionResult(BaseModel):
    trace_id:        str
    failing_agent:   str
    failing_action:  str
    call_tree_depth: int
    mast_category:   int      # 1, 2, or 3
    signature_name:  str
    fix_direction:   str
    confidence:      float
```

## SilentFailureResult (SC2)
```python
class SilentFailureResult(BaseModel):
    trace_id:          str
    pattern:           str    # "infinite_retry_loop","entropy_collapse","token_burn"
    evidence:          str    # what the analyst found
    cost_anomaly_ratio: float # actual/expected cost
    detected:          bool
```

## CrossLayerResult (SC3)
```python
class CrossLayerResult(BaseModel):
    trace_id:          str
    agent_reported_calls: int
    host_observed_calls:  int
    delta:             int
    severity:          str   # "none","low","medium","high","critical"
    evidence:          str
```

## Analyst interface
```python
class AnalystManager:
    async def attribute_failure(self, trace_id: str) -> AttributionResult: ...
    async def detect_silent_failure(self, trace_id: str) -> SilentFailureResult: ...
    async def check_cross_layer(self, trace_id: str) -> CrossLayerResult: ...
    async def full_report(self, trace_id: str) -> dict: ...
```

## Gate requirements (gate_12_analyst.py)
- SC1: attribute_failure() returns correct failing_agent="worker-b" for test trace
- SC1: mast_category=2 for conflicting parallel outputs scenario
- SC2: detect_silent_failure() returns detected=True for infinite retry trace
- SC3: check_cross_layer() returns delta>0 when host sees more connections than agent reported
- full_report() returns all three results in one dict
