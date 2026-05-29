<div align="center">

```
 █████╗  ██████╗ ███████╗███╗   ██╗████████╗
██╔══██╗██╔════╝ ██╔════╝████╗  ██║╚══██╔══╝
███████║██║  ███╗█████╗  ██╔██╗ ██║   ██║
██╔══██║██║   ██║██╔══╝  ██║╚██╗██║   ██║
██║  ██║╚██████╔╝███████╗██║ ╚████║   ██║
╚═╝  ╚═╝ ╚═════╝ ╚══════╝╚═╝  ╚═══╝   ╚═╝
██╗    ██╗ █████╗ ████████╗ ██████╗██╗  ██╗
██║    ██║██╔══██╗╚══██╔══╝██╔════╝██║  ██║
██║ █╗ ██║███████║   ██║   ██║     ███████║
██║███╗██║██╔══██║   ██║   ██║     ██╔══██║
╚███╔███╔╝██║  ██║   ██║   ╚██████╗██║  ██║
 ╚══╝╚══╝ ╚═╝  ╚═╝   ╚═╝    ╚═════╝╚═╝  ╚═╝
```

**Security observability for AI agent systems.**  
*Catch what LangSmith can't. Stop attacks before they propagate.*

[![Python 3.12](https://img.shields.io/badge/python-3.12-3776ab?style=flat-square&logo=python&logoColor=white)](https://www.python.org/downloads/)
[![Tests](https://img.shields.io/badge/tests-207%20passing-22c55e?style=flat-square)](#testing)
[![License: MIT](https://img.shields.io/badge/license-MIT-f59e0b?style=flat-square)](LICENSE)
[![arXiv](https://img.shields.io/badge/arXiv-2503.13657-b31b1b?style=flat-square)](https://arxiv.org/abs/2503.13657)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![ClickHouse](https://img.shields.io/badge/ClickHouse-append--only-FFCC01?style=flat-square)](https://clickhouse.com)

</div>

---

## The $47,000 problem

```
span 001  status=ok  summary="processing request..."   cost=$0.0004
span 002  status=ok  summary="processing request..."   cost=$0.0004
span 003  status=ok  summary="processing request..."   cost=$0.0004
...
span 150  status=ok  summary="processing request..."   cost=$0.0004
                                               total: ──────────────
                                                            $47.23
```

Your agent looped 150 times. Every span reported `ok`. No errors. No alerts.  
LangSmith was green. Langfuse was green. You got the bill.

**AgentWatch detected the loop on span 11.**

---

## What existing tools miss

| Capability | LangSmith | Langfuse | **AgentWatch** |
|------------|:---------:|:--------:|:--------------:|
| Trace visualization | ✅ | ✅ | ✅ |
| Cost tracking | ✅ | ✅ | ✅ |
| **Silent failure detection** (all-ok loops) | ❌ | ❌ | ✅ |
| **Coordination failure attribution** (MAST) | ❌ | ❌ | ✅ |
| **Cross-layer OS/signal discrepancy** | ❌ | ❌ | ✅ |
| **Memory integrity** (MINJA / SpAIware) | ❌ | ❌ | ✅ |
| **Default-deny policy engine** | ❌ | ❌ | ✅ |
| **Interceptor** (halt / quarantine / revoke) | ❌ | ❌ | ✅ |
| **HMAC-verified signal origin** | ❌ | ❌ | ✅ |

---

## Three proof scenarios

<table>
<tr>
<td width="33%">

### SC1 — Coordination failure

Orchestrator delegates to parallel workers. Worker B returns `error: conflicting instruction`.

AgentWatch attributes the failure to the **exact agent**, maps it to **MAST Category 2** (inter-agent misalignment), identifies call tree depth, and emits a fix direction.

</td>
<td width="33%">

### SC2 — Silent failure

Agent loops 150 times. All spans `status=ok`. Identical summaries. Zero alerts from LangSmith or Langfuse.

AgentWatch detects `infinite_retry_loop`, computes `cost_anomaly_ratio=10.0×`, fires **on span 11**.

</td>
<td width="33%">

### SC3 — Cross-layer discrepancy

Agent self-reports **1** network call. Sysmon logs **3** TCP connections for the same `process_guid`.

`Δ = 2`. Severity = **HIGH**. The agent lied — or was compromised. AgentWatch catches the gap.

</td>
</tr>
</table>

---

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│                     Your AI Agents                        │
│          orchestrator → worker-a, worker-b, tools         │
└───────────────────────────┬──────────────────────────────┘
                            │ HMAC-signed signals
                            ▼
╔══════════════════════════════════════════════════════════╗
║                      A G E N T W A T C H                 ║
║                                                          ║
║  ┌─────────────┐  ┌────────────┐  ┌───────────────────┐ ║
║  │   Receiver  │  │  Discovery │  │   Policy Engine   │ ║
║  │ HMAC verify │  │  Scanner   │  │   default-deny    │ ║
║  └──────┬──────┘  └────────────┘  └───────────────────┘ ║
║         │                                                ║
║         ▼                                                ║
║  ┌─────────────┐  ┌────────────┐  ┌───────────────────┐ ║
║  │   Content   │  │   Memory   │  │     Chronicle     │ ║
║  │  Inspector  │  │  Integrity │  │  ClickHouse · TTL │ ║
║  │ 15 patterns │  │MINJA/SpAIw │  │   append-only     │ ║
║  └─────────────┘  └────────────┘  └───────────────────┘ ║
║                                                          ║
║  ┌─────────────┐  ┌────────────┐  ┌───────────────────┐ ║
║  │ Behavioral  │  │   Coord    │  │     Analyst       │ ║
║  │  Baseline   │  │ Signatures │  │   SC1 · SC2 · SC3 │ ║
║  │  3σ alerts  │  │ 19 MAST+   │  │   attribution     │ ║
║  └─────────────┘  └────────────┘  └───────────────────┘ ║
║                                                          ║
║  ┌─────────────┐  ┌────────────┐  ┌───────────────────┐ ║
║  │    Host     │  │   Verdict  │  │   Interceptor     │ ║
║  │  Telemetry  │  │   Engine   │  │ halt · quarantine │ ║
║  │Sysmon/Falco │  │  3-stage   │  │      revoke       │ ║
║  └─────────────┘  └────────────┘  └───────────────────┘ ║
║                                                          ║
║  ══════════════  FastAPI · port 8000  ════════════════   ║
╚══════════════════════════════════════════════════════════╝
```

**16 layers. Sequential gates. Each must pass before the next builds.**  
See [ARCHITECTURE.md](ARCHITECTURE.md) for full detail.

---

## Quickstart

```bash
# 1. Start infrastructure
docker compose up -d redis clickhouse postgres neo4j

# 2. Install
python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"

# 3. Run all 16 gate tests
make gate-all

# 4. Run the three proof scenarios
make poc

# 5. Start the API
make api
```

> API docs live at **http://localhost:8000/docs** (Swagger UI)

Full setup: [docs/QUICKSTART.md](docs/QUICKSTART.md)  
Production deployment: [docs/PRODUCTION_INTEGRATION.md](docs/PRODUCTION_INTEGRATION.md)

---

## Key API endpoints

```bash
# Health — all infra components
GET  /api/v1/health

# Full analyst report for any trace (SC1 + SC2 + SC3)
GET  /api/v1/analyst/report/{trace_id}

# Silent failures detected in last N hours
GET  /api/v1/analyst/silent-failures?hours=24

# MAST + infra topology risk signatures (19 patterns)
GET  /api/v1/analyst/topology-risks

# Quarantine an agent (logged to Chronicle, irrevocable)
POST /api/v1/interceptor/quarantine
     {"agent_id": "worker-b", "reason": "MAST C2", "trigger": "analyst"}

# Rebuild full trace from Chronicle
GET  /api/v1/traces/{trace_id}

# Agent verdict history
GET  /api/v1/agents/{agent_id}/verdicts
```

Full reference: [docs/API.md](docs/API.md)

---

## Detection capabilities

### Memory Integrity Monitor (MIM)

| Attack | Description | Detection |
|--------|-------------|-----------|
| **MINJA** | Memory INJection Attack — query-only poisoning | Bridging query → indication → self-write sequence |
| **SpAIware** | Cross-session malware propagation | Content fingerprint repeats across session boundaries |

14 regex patterns. Fires on `high`/`critical` severity only.

### Coordination Signatures (MAST)

Based on [arXiv:2503.13657](https://arxiv.org/abs/2503.13657) — NeurIPS 2025 Spotlight — Cohen's κ=0.88 across 1,642 annotated traces.

```
Category 1 — Specification     task misinterpretation · role ambiguity · poor decomposition
                                duplicate roles · missing termination condition

Category 2 — Inter-agent       handoff breakdown · context loss · conflicting parallel outputs
                                format mismatch between agents

Category 3 — Verification      premature termination · incomplete verification · incorrect logic
                                missing error recovery · no feedback loop

Infrastructure                  infinite retry loop · rate limit cascade · context overflow
                                API version drift · framework misuse
```

### Verdict Engine

```
Stage 1 — Deterministic   cost > $0.10 · spans > 50 · any framework_fault · policy violation
               ↓ (if not conclusive)
Stage 2 — Baseline        3σ deviation from per-agent behavioral profile (50-trace window)
               ↓ (sampled 20%)
Stage 3 — LLM Judge       receives summarized trace only — never raw spans
```

### Content Inspector

15 regex patterns covering:
- Direct instruction injection (`ignore previous instructions`, `[INST]` blocks)
- System/role override (`SYSTEM:`, `you are now`, `you are unrestricted`)
- Jailbreaks (`DAN`, `forget training`, `no rules apply`)
- Exfiltration (`send * to https://`, `forward credentials to`)
- Bypass attempts (`override safety`, `disregard guidelines`)

---

## Security invariants

These are enforced in code and verified in every gate run:

```
✦  Chronicle is APPEND-ONLY. No UPDATE. No DELETE. Ever.
✦  Signal origin HMAC-verified on every emission, not just the first.
✦  Policy Engine is DEFAULT-DENY. Must be permitted, not just not forbidden.
✦  Interceptor logs EVERY ACTION to Chronicle. Never silent.
✦  New agent runs in RESTRICTED MODE until 50 traces establish baseline.
✦  LLM Judge receives SUMMARIZED TRACE — never raw spans.
```

---

## Testing

```
Tier 1 — Must-detect      12 tests · zero tolerance · any miss = CRITICAL security gap
Tier 2 — False positives  14 tests · FP rate must be 0% on corpus
Tier 3 — Scenario/gates  207 tests · 8 attack scenarios · 16 gate layers
Tier 4 — Agentic tester   Claude-generated novel payloads · target DR ≥ 90%
```

```bash
# Run all 207 static tests
make test

# Run gate suite (stops on first failure)
make gate-all

# Agentic tester — requires ANTHROPIC_API_KEY
python -m agents.agentic_tester

# Agentic tester — no API key needed
python -m agents.agentic_tester --mock
```

Pass criteria: [docs/SUCCESS_CRITERIA.md](docs/SUCCESS_CRITERIA.md)  
Failure history: [docs/FAILURE_LOG.md](docs/FAILURE_LOG.md)

---

## Infrastructure

| Component | Role | Default |
|-----------|------|---------|
| **Redis** | Signal stream (`wt:signals`), interceptor bus, memory event bus | `:6379` |
| **ClickHouse** | Chronicle — append-only event store, 90-day TTL | `:8123` |
| **PostgreSQL** | Behavioral baseline, policy store | `:5432` |
| **Neo4j** | Access graph — agent trust topology, blast radius | `:7687` |

---

## Project structure

```
watchtower/
├── core/               Signal, Trace, EventType — shape defined once, never duplicated
├── discovery/          Agent scanner + registry
├── access_graph/       Permission graph, blast radius calculation
├── policy_engine/      Default-deny + temporal ordering constraints
├── content_inspection/ 15-pattern IPI / jailbreak / exfil detector
├── receiver/           HMAC verification layer
├── memory_monitor/     MINJA + SpAIware detectors
├── chronicle/          ClickHouse append-only writer + reader
├── verdict/            3-stage verdict engine (deterministic → baseline → LLM)
├── baseline/           Per-agent behavioral profiling (3σ)
├── coord_sigs/         19 MAST + infra signature library
├── analyst/            SC1 attribution · SC2 silent failure · SC3 cross-layer
├── interceptor/        Halt · quarantine · revoke
├── host_telemetry/     Sysmon XML + Falco JSON parsers + process correlator
└── api/                FastAPI routers + schemas

agents/
└── agentic_tester/     4-agent Claude-powered adversarial test system
    ├── agents/         ReconAgent · PlannerAgent · ExecutorAgent · AnalystAgent
    ├── orchestrator.py Multi-agent orchestration loop
    └── mock_payloads.py 58 curated payloads for --mock mode (no API key needed)

docs/
├── QUICKSTART.md
├── API.md
├── PRODUCTION_INTEGRATION.md  10-phase deployment guide
├── SUCCESS_CRITERIA.md        Pass/fail definitions, all tiers
├── FAILURE_LOG.md             22 failures documented with root cause + fix
└── TESTING_GAPS.md            Generated by agentic tester
```

---

## Citation

```bibtex
@inproceedings{cohen2025mast,
  title   = {MAST: A Multi-Agent System Taxonomy for LLM Failure Mode Classification},
  author  = {Cohen et al.},
  booktitle = {NeurIPS 2025},
  note    = {arXiv:2503.13657, Spotlight}
}
```

---

## Contributing

[CONTRIBUTING.md](CONTRIBUTING.md) — adding signatures, detectors, and new layers.

## License

MIT
