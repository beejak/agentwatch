# Architecture

## Overview

AgentWatch is a **passive, append-only, 16-layer observability system** that sits beside your agent infrastructure without modifying it. Agents emit HMAC-signed signals to a Redis stream. AgentWatch consumes, analyzes, and acts — independently of the agents being observed.

```
Agents ──(HMAC signals)──► Redis wt:signals ──► Receiver ──► 15 downstream layers
                                                                      │
                                                              Chronicle (ClickHouse)
                                                              append-only, 90-day TTL
```

---

## Layer Map

| # | Layer | Purpose | Key files |
|---|-------|---------|-----------|
| 01 | **Core** | Signal shape — OTel-compatible, defined once | `core/signal.py` |
| 02 | **Discovery** | Namespace polling, unknown agent detection | `discovery/scanner.py` |
| 03 | **Access Graph** | Permission topology, blast radius | `access_graph/graph.py` |
| 04 | **Policy Engine** | Default-deny + BEFORE/AFTER temporal constraints | `policy_engine/engine.py` |
| 05 | **Content Inspection** | 12-pattern IPI/jailbreak/role-override scanner | `content_inspection/inspector.py` |
| 06 | **Receiver** | HMAC-SHA256 verify on every signal | `receiver/verification.py` |
| 07 | **Memory Integrity Monitor** | MINJA sequence + SpAIware cross-session detection | `memory_monitor/monitor.py` |
| 08 | **Chronicle** | ClickHouse append-only store, 8 event tables | `chronicle/writer.py` |
| 09 | **Verdict Engine** | 3-stage judgment: deterministic → baseline → LLM | `verdict/engine.py` |
| 10 | **Behavioral Baseline** | Per-agent profile, 3σ deviation, restricted mode | `baseline/engine.py` |
| 11 | **Coordination Signatures** | 14 MAST + 5 infra patterns, topology matching | `coord_sigs/library.py` |
| 12 | **Analyst** | SC1/SC2/SC3 sub-agents: attribution, silent, cross-layer | `analyst/manager.py` |
| 13 | **Interceptor** | Halt, quarantine, revoke — every action Chronicle-logged | `interceptor/interceptor.py` |
| 14 | **POC** | Three proof scenarios, composite scoring | `tests/poc/` |
| 15 | **FastAPI** | REST API: traces, analyst, interceptor | `api/main.py` |
| 16 | **Host Telemetry** | Sysmon XML + Falco JSON parsers, process_guid correlation | `host_telemetry/sysmon.py` |

---

## Data Flow

```
┌─────────────────────────────────────────────────────────────┐
│  Agent emits Signal (20 fields, HMAC-signed)                │
│  → Redis stream wt:signals                                  │
└──────────────────────────┬──────────────────────────────────┘
                           │
                    ┌──────▼──────┐
                    │  Receiver   │  HMAC verify every signal
                    │  Layer 06   │  Reject if tampered
                    └──────┬──────┘
                           │
          ┌────────────────┼────────────────┐
          │                │                │
   ┌──────▼──────┐  ┌──────▼──────┐  ┌─────▼───────┐
   │  Discovery  │  │   Content   │  │   Memory    │
   │  Layer 02   │  │ Inspection  │  │  Integrity  │
   │             │  │  Layer 05   │  │  Layer 07   │
   └──────┬──────┘  └──────┬──────┘  └─────┬───────┘
          │                │                │
          └────────────────┼────────────────┘
                           │
                    ┌──────▼──────┐
                    │  Chronicle  │  Append-only ClickHouse
                    │  Layer 08   │  8 event tables, 90-day TTL
                    └──────┬──────┘
                           │
          ┌────────────────┼────────────────┐
          │                │                │
   ┌──────▼──────┐  ┌──────▼──────┐  ┌─────▼───────┐
   │   Verdict   │  │  Baseline   │  │Coord Sigs   │
   │  Layer 09   │  │  Layer 10   │  │  Layer 11   │
   └──────┬──────┘  └──────┬──────┘  └─────┬───────┘
          │                │                │
          └────────────────┼────────────────┘
                           │
                    ┌──────▼──────┐
                    │   Analyst   │  SC1: attribution
                    │  Layer 12   │  SC2: silent failure
                    │             │  SC3: cross-layer
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │ Interceptor │  halt / quarantine / revoke
                    │  Layer 13   │  blast radius propagation
                    └─────────────┘
```

---

## Signal Shape

Every signal is an OTel-compatible Pydantic model. Shape defined **once** in `watchtower/core/signal.py` — never duplicated.

```python
class Signal(BaseModel):
    # Trace context
    trace_id:        str           # UUID, groups all spans in one logical operation
    span_id:         str           # UUID, unique to this span
    parent_span_id:  Optional[str] # Links to caller span

    # Agent identity
    agent_id:        str           # Who emitted this signal
    caller_agent_id: Optional[str] # Which agent triggered this one

    # Action
    action:          str           # "llm_call","tool_use","handoff","delegate",...
    status:          str           # "ok","error","timeout"
    summary:         str           # Human-readable description

    # Timing + cost
    timestamp:       float         # Unix epoch
    duration_ms:     float
    tokens_in:       int
    tokens_out:      int
    model:           Optional[str]
    cost:            float

    # Security + observability
    instruction_hash: Optional[str] # SHA256 of instruction text — detects drift
    process_guid:     Optional[str] # OS process GUID — cross-layer correlation
    retrieval_flag:   bool          # True if RAG retrieval occurred
    memory_op:        Optional[str] # "read","write","delete"
    framework_fault:  bool          # True if framework (not agent) caused error
    policy_checked:   bool          # True if policy engine evaluated this action
```

---

## Chronicle Schema

8 ClickHouse MergeTree tables. All append-only. 90-day TTL. No UPDATE. No DELETE. Ever.

```
watchtower.agent_spans       ← primary signal store
watchtower.host_telemetry    ← Sysmon/Falco events
watchtower.memory_events     ← MIM write/read events
watchtower.content_results   ← content inspection hits
watchtower.policy_decisions  ← allow/deny log
watchtower.verdicts          ← verdict engine outputs
watchtower.interceptor_acts  ← every halt/quarantine/revoke
watchtower.discovery_events  ← new/unknown agent detections
```

---

## Access Graph

Neo4j bolt graph. Nodes = agents. Edges = permitted call relationships (from manifests). Used for:

- **Pre-action permission check**: is agent A allowed to call agent B?
- **Blast radius query**: if agent X is quarantined, which downstream agents are affected?
- **Topology matching**: coordination signature library compares trace topology against MAST patterns

---

## Policy Engine

Default-deny. Every action must be **explicitly permitted** — not just not forbidden.

Supports temporal constraints:
- `BEFORE(action_b)`: action_a must occur before action_b
- `AFTER(action_a)`: action_b requires action_a to have completed
- `MAX_FREQUENCY(n, window)`: at most n occurrences per time window

---

## Verdict Engine

```
┌─────────────────────────────────────────────────────┐
│  Stage 1: Deterministic (always runs)               │
│  - Cost > threshold?                                │
│  - Step count > limit?                              │
│  - Permission violation?                            │
│  → conclusive: early exit with score=0.0            │
└──────────────────────────┬──────────────────────────┘
                           │ not conclusive
┌──────────────────────────▼──────────────────────────┐
│  Stage 2: Baseline deviation (always runs)          │
│  - Compare against per-agent behavioral profile     │
│  - 3σ threshold on cost, step count, token ratio    │
│  - New agents: restricted mode until 50 traces      │
│  → conclusive: early exit with score=0.0            │
└──────────────────────────┬──────────────────────────┘
                           │ not conclusive
┌──────────────────────────▼──────────────────────────┐
│  Stage 3: LLM Judge (sampled at 20%)                │
│  - Receives TraceSummariser output, NOT raw spans   │
│  - Summariser keeps: first, last, errors, handoffs  │
│  - All other spans sampled                          │
│  → verdict with score, source, reason               │
└─────────────────────────────────────────────────────┘
```

---

## Memory Integrity Monitor

### MINJA (Memory INJection Attack)
Detects query-only self-poisoning — a 3-step attack:
1. **Bridging query**: benign-looking memory read
2. **Indication prompt**: `SYSTEM:` prefix or role-override language written to memory
3. **Exfiltration write**: instruction-like content (ignore/override/exfil patterns)

Detection: sliding 20-event window per agent, pattern matches across sequence.

### SpAIware
Cross-session content planting. If flagged content (hash) appears in a different session for the same agent, it's cross-session repeat — escalates severity from `high` → `critical`.

---

## Host Telemetry (Cross-Layer, SC3)

Sysmon EventID 3 (network connection) events are parsed and correlated to agent spans via `process_guid`. When:

- Agent reports N network calls in a span
- Sysmon shows M network connections for same `process_guid`
- M > N: delta = M - N → **discrepancy detected**

This is the only detection vector that catches a compromised or lying agent — because the agent cannot forge OS-level telemetry.

---

## Security Invariants

| Invariant | Where enforced |
|-----------|---------------|
| Chronicle append-only | ClickHouse MergeTree, no mutation queries ever issued |
| Signal HMAC on every emission | `receiver/verification.py`, checked before any processing |
| Default-deny policy | `policy_engine/engine.py`, missing permission = deny |
| Interceptor always logs | `interceptor/interceptor.py`, Chronicle write before return |
| LLM Judge never sees raw spans | `verdict/summariser.py` always called first |
| New agent restricted mode | `baseline/engine.py`, < 50 traces = restricted |
