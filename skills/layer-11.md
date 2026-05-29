# SKILL: Layer 11 — Coordination Signature Library

## Job
Match live agent topologies against known failure patterns.
Predict failures BEFORE they occur.
Sources: MAST (14 modes), Aegis (6 modes), infrastructure (5 patterns).

## Files to create
- watchtower/coord_sigs/library.py       — loads signatures, runs matcher
- watchtower/coord_sigs/signatures/mast.yaml
- watchtower/coord_sigs/signatures/aegis.yaml
- watchtower/coord_sigs/signatures/infra.yaml
- watchtower/coord_sigs/matcher.py       — topology matcher

## SignatureMatch model
```python
class SignatureMatch(BaseModel):
    signature_id:   str
    category:       str    # "mast_spec","mast_alignment","mast_verify","aegis","infra"
    name:           str
    risk_level:     str    # "low","medium","high","critical"
    description:    str
    fix_direction:  str
    matched_agents: list[str]
    confidence:     float
```

## Library interface
```python
class CoordSignatureLibrary:
    async def load(self) -> None: ...
    async def match_topology(self, spans: list[Signal]) -> list[SignatureMatch]: ...
```

## MAST signatures to put in mast.yaml (14 total)
Category 1 - Specification (41.8%):
  - task_misinterpretation
  - role_ambiguity  
  - poor_decomposition
  - duplicate_roles
  - missing_termination

Category 2 - Inter-agent misalignment (36.9%):
  - handoff_breakdown
  - context_loss
  - conflicting_parallel_outputs  ← SC1 scenario uses this
  - format_mismatch

Category 3 - Verification gaps (21.3%):
  - premature_termination
  - incomplete_verification
  - incorrect_verification_logic
  - missing_error_recovery
  - no_feedback_loop

## Infrastructure patterns in infra.yaml
- infinite_retry_loop         ← SC2 scenario uses this
- rate_limit_cascade
- context_window_overflow
- api_version_drift
- framework_api_misuse

## Gate requirements (gate_11_coord.py)
- All 14 MAST modes load without error
- Orchestrator→parallel workers topology → matches "conflicting_parallel_outputs"
- Sequential A→B→C → matches "no_feedback_loop"
- Same output repeated → matches "infinite_retry_loop"
- Match produces SignatureMatch with risk_level + fix_direction populated
