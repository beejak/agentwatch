# SKILL: Layer 14 — Integration + POC Scenarios

## Job
End-to-end scenarios proving the three proof questions.
Benchmark comparison vs LangSmith baseline.

## Files to create
- tests/poc/scenario_01_coordination.py  — SC1: coordination failure
- tests/poc/scenario_02_silent.py        — SC2: silent failure (infinite retry)
- tests/poc/scenario_03_crosslayer.py    — SC3: cross-layer discrepancy
- tests/benchmark/test_gap.py            — LangSmith gap documentation

## SC1 — Coordination Failure
Setup: orchestrator → worker-a + worker-b (parallel)
      worker-b fails with status="error"
      conflicting_parallel_outputs MAST C2 signature

WatchTower must answer: failing_agent="worker-b", mast_category=2

## SC2 — Silent Failure (the $47K scenario)
Setup: agent in retry loop
      status="ok" on all spans
      same output summary repeated 5 times
      tokens: 50x normal baseline cost

WatchTower must answer: pattern="infinite_retry_loop", detected=True

## SC3 — Cross-Layer Discrepancy  
Setup: agent reports 1 network call in signal
      Sysmon file shows 3 outbound connections from same process_guid
      host_telemetry Chronicle has 3 events

WatchTower must answer: delta=2, severity="high"

## Benchmark comparison
LangSmith baseline for same 3 scenarios:
- SC1: LangSmith shows error span but NO mast_category, NO fix_direction
- SC2: LangSmith shows "ok" status (green dashboard, misses it)
- SC3: LangSmith has no host_telemetry concept (cannot answer)

Document gap as: LangSmith_result vs WatchTower_result per scenario

## Gate requirements (gate_14_poc.py)
- All 3 scenarios run end-to-end
- SC1 Q1 answered correctly from Chronicle query alone
- SC2 detected with correct pattern name
- SC3 delta and severity correct
- All layers produced events in Chronicle (verify 8 event streams)
- Benchmark comparison produces side-by-side gap table
