# Proof Scenarios

Three scenarios that demonstrate what AgentWatch detects that no existing tool can.

Run all three: `make poc`

---

## SC1 — Coordination Failure Attribution

**File:** `tests/poc/scenario_01_coordination.py`

### Setup

An orchestrator delegates a task to two parallel workers. Worker A completes successfully. Worker B returns an error with `"conflicting instruction"`.

```
orchestrator (delegate)
├── worker-a (llm_call) → status: ok, summary: "result: option A"
└── worker-b (llm_call) → status: error, summary: "error: conflicting instruction"
```

### What AgentWatch detects

1. **Error attribution**: `worker-b` identified as failing agent
2. **MAST category**: Category 2 (Inter-agent Misalignment)
3. **Signature**: `mast_c2_conflicting_parallel_outputs`
4. **Call tree depth**: 2 (workers are children of orchestrator)
5. **Fix direction**: "Add consensus/merge step; define conflict resolution strategy"

### Composite scoring (gate threshold: 0.80)

| Criterion | Weight | Pass condition |
|-----------|--------|----------------|
| MAST category identified | 0.40 | category in {1, 2, 3} |
| Failing agent identified | 0.30 | not "unknown" |
| Call tree depth ≥ 2 | 0.20 | depth ≥ 2 |
| Fix direction present | 0.10 | non-empty string |

### What LangSmith sees

A trace with one error span. No MAST classification. No call tree depth. No fix direction. You know *something* failed. You don't know *what kind* of failure, *where* in the call graph, or *how to fix it*.

---

## SC2 — Silent Failure Detection

**File:** `tests/poc/scenario_02_silent.py`

### Setup

An agent runs 150 LLM calls. Every single one returns `status: ok`. The summary is identical across all 150 spans: `"retry attempt: same output repeated"`.

```
looping-agent (llm_call) → ok  ─┐
looping-agent (llm_call) → ok   │
looping-agent (llm_call) → ok   │  × 150
...                              │
looping-agent (llm_call) → ok  ─┘
```

No errors. No exceptions. No alerts from any conventional tool.

### What AgentWatch detects

```json
{
  "pattern": "infinite_retry_loop",
  "detected": true,
  "cost_anomaly_ratio": 10.0,
  "evidence": "150 spans, summary 'retry attempt: same output repeated' repeated 150 times, no errors (silent)"
}
```

Detection fires at span 11 (after `MIN_SPANS_FOR_LOOP=10` with 3+ repeated summaries).

### The "$47K" extrapolation

| Scale | Spans | Cost per run | Daily (100 runs) |
|-------|-------|-------------|-----------------|
| This test | 150 | $0.068 | $6.75 |
| 10 parallel agents | 1,500 | $0.68 | $67.50 |
| 100 parallel agents | 15,000 | $6.75 | $675 |
| Production (1,000 agents) | 150,000 | $67.50 | $6,750 |
| Monthly (30 days) | — | — | **$202,500** |

A real-world "$47K mistake" is 7 hours of 1,000 agents in a loop. All status: ok.

### What LangSmith sees

150 green spans. A very long trace. No alerts. Maybe a cost spike in the weekly report.

---

## SC3 — Cross-Layer Discrepancy

**File:** `tests/poc/scenario_03_crosslayer.py`

### Setup

An agent makes one API call. That's what it reports. But the Sysmon log for the same process shows 3 TCP network connections (EventID 3) — same `process_guid`.

**Agent signal:**
```json
{
  "agent_id": "suspicious-agent",
  "action": "api_call",
  "summary": "called external API once",
  "process_guid": "abc123-..."
}
```

**Sysmon XML (3 EventID 3 entries for same process_guid):**
```xml
<Event>
  <EventData>
    <Data Name="ProcessGuid">abc123-...</Data>
    <Data Name="DestinationIp">203.0.113.1</Data>
  </EventData>
</Event>
<!-- × 3 -->
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

The agent cannot forge Sysmon logs. They come from the Windows kernel driver (or Falco on Linux). If the agent says 1 and the OS says 3, either:
- The agent is compromised and hiding calls
- A side-channel is exfiltrating data
- Framework code is making unreported calls

Delta ≥ 2 = severity `high`. Automatically triggers Interceptor recommendation.

### What LangSmith sees

One api_call span. Status ok. Nothing unusual. The 2 unreported network calls are invisible.

---

## Running scenarios manually

```bash
# SC1 only
.venv/bin/python -m pytest tests/poc/scenario_01_coordination.py -v

# SC2 only  
.venv/bin/python -m pytest tests/poc/scenario_02_silent.py -v

# SC3 only
.venv/bin/python -m pytest tests/poc/scenario_03_crosslayer.py -v

# All three
make poc
```

### Expected output

```
tests/poc/scenario_01_coordination.py::test_sc1_coordination_failure PASSED
tests/poc/scenario_02_silent.py::test_sc2_silent_failure_detection PASSED
tests/poc/scenario_03_crosslayer.py::test_sc3_cross_layer_discrepancy PASSED
```
