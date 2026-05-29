# Proof Scenarios

Three scenarios demonstrating what AgentWatch detects that no existing tool can.

```bash
make poc   # run all three
```

---

## SC1 — Coordination Failure Attribution

**File:** `tests/poc/scenario_01_coordination.py`

### The setup

An orchestrator delegates a task to two parallel workers. Worker A completes. Worker B errors.

```
orchestrator (delegate)
├── worker-a (llm_call) ──→ status: ok    "result: option A"
└── worker-b (llm_call) ──→ status: error "error: conflicting instruction"
```

### What AgentWatch detects

```json
{
  "failing_agent": "worker-b",
  "failing_action": "llm_call",
  "call_tree_depth": 2,
  "mast_category": 2,
  "signature_name": "Conflicting Parallel Outputs",
  "fix_direction": "Add consensus/merge step; define conflict resolution strategy",
  "confidence": 0.85
}
```

### Composite scoring (gate threshold: ≥ 0.80)

| Criterion | Weight | Pass condition |
|-----------|--------|----------------|
| MAST category identified | 0.40 | category in {1, 2, 3} |
| Failing agent identified | 0.30 | not `"unknown"` |
| Call tree depth ≥ 2 | 0.20 | depth ≥ 2 |
| Fix direction present | 0.10 | non-empty string |

### What LangSmith sees

A trace with one error span. No MAST classification. No call tree depth. No fix direction.  
You know *something* failed. You don't know *what kind*, *where*, or *how to fix it*.

---

## SC2 — Silent Failure Detection

**File:** `tests/poc/scenario_02_silent.py`

### The setup

An agent runs 150 LLM calls. Every single one returns `status: ok`. Identical summaries throughout.

```
looping-agent (llm_call) → ok  ─┐
looping-agent (llm_call) → ok   │
looping-agent (llm_call) → ok   │  × 150 spans
...                              │
looping-agent (llm_call) → ok  ─┘

No errors. No exceptions. No alerts from any conventional tool.
```

### What AgentWatch detects

```json
{
  "pattern": "infinite_retry_loop",
  "detected": true,
  "cost_anomaly_ratio": 10.0,
  "evidence": "150 spans, summary 'retry attempt: same output repeated' repeated 150 times, no errors (silent)"
}
```

Detection fires at **span 11** — after `MIN_SPANS_FOR_LOOP=10` with 3+ repeated summaries.

### The cost extrapolation

| Scale | Spans/run | Cost/run | Daily (100 runs) |
|-------|-----------|----------|-----------------|
| This test | 150 | $0.068 | $6.75 |
| 10 parallel agents | 1,500 | $0.68 | $67.50 |
| 100 parallel agents | 15,000 | $6.75 | $675 |
| Production (1,000 agents) | 150,000 | $67.50 | $6,750 |
| **Monthly (30 days)** | — | — | **$202,500** |

A real-world "$47K mistake" is 7 hours of 1,000 agents in a loop. All `status: ok`.

### What LangSmith sees

150 green spans. A very long trace. No alerts.  
Maybe a cost spike in next week's billing report.

---

## SC3 — Cross-Layer Discrepancy

**File:** `tests/poc/scenario_03_crosslayer.py`

### The setup

An agent makes one API call — that's what it reports. Sysmon logs 3 TCP connections for the same `process_guid`.

**Agent signal:**
```json
{
  "agent_id": "suspicious-agent",
  "action": "api_call",
  "summary": "called external API once",
  "process_guid": "abc123-..."
}
```

**Sysmon telemetry (3 × EventID 3 for same process_guid):**
```xml
<Event>
  <System><EventID>3</EventID></System>
  <EventData>
    <Data Name="ProcessGuid">abc123-...</Data>
    <Data Name="DestinationIp">203.0.113.1</Data>
  </EventData>
</Event>
```

### What AgentWatch detects

```json
{
  "agent_reported_calls": 1,
  "host_observed_calls": 3,
  "delta": 2,
  "severity": "high",
  "evidence": "Agent reported 1 network call; host shows 3 for process_guid abc123-..."
}
```

### Why this matters

The agent **cannot forge Sysmon logs**. They come from the Windows kernel driver (or Falco on Linux). If the agent says 1 and the OS says 3:

- The agent is **compromised** and hiding calls
- A **side-channel** is exfiltrating data
- **Framework code** is making unreported calls

**Severity mapping:**

| Delta | Severity |
|-------|----------|
| 0 | none |
| 1 | medium |
| ≥ 2 | **high** |
| ≥ 5 | **critical** |

### What LangSmith sees

One `api_call` span. Status `ok`. Nothing unusual.  
The 2 unreported network connections are completely invisible.

---

## Running scenarios individually

```bash
# SC1 — coordination failure
.venv/bin/python -m pytest tests/poc/scenario_01_coordination.py -v

# SC2 — silent failure
.venv/bin/python -m pytest tests/poc/scenario_02_silent.py -v

# SC3 — cross-layer discrepancy
.venv/bin/python -m pytest tests/poc/scenario_03_crosslayer.py -v
```

### Expected output

```
tests/poc/scenario_01_coordination.py::test_sc1_coordination_failure  PASSED
tests/poc/scenario_02_silent.py::test_sc2_silent_failure_detection    PASSED
tests/poc/scenario_03_crosslayer.py::test_sc3_cross_layer_discrepancy PASSED
```

---

## Full attack scenario coverage

Beyond the 3 proof scenarios, AgentWatch covers 8 full attack scenarios in `tests/scenarios/`:

| Scenario | File | What it tests |
|----------|------|---------------|
| SC4 | `test_sc4_tool_injection.py` | Injection via tool output |
| SC5 | `test_sc5_agent_impersonation.py` | Caller identity spoofing |
| SC6 | `test_sc6_instruction_drift.py` | Mid-trace instruction reprogramming |
| SC7 | `test_sc7_context_overflow.py` | Token burn attack |
| SC8 | `test_sc8_rate_limit_cascade.py` | Framework fault escalation |
| SC9 | `test_sc9_memory_exfil.py` | Covert data exfiltration via memory |
| SC10 | `test_sc10_policy_bypass.py` | Authorization boundary violation |
| SC11 | `test_sc11_multihop_poison.py` | Multi-agent propagation chain |
