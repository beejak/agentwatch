# AgentWatch

**Multi-layer observability and security for LLM agent systems.**

[![CI](https://github.com/agentwatch/agentwatch/actions/workflows/ci.yml/badge.svg)](https://github.com/agentwatch/agentwatch/actions/workflows/ci.yml)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![arXiv](https://img.shields.io/badge/arXiv-2503.13657-b31b1b.svg)](https://arxiv.org/abs/2503.13657)

---

## The problem

Your agent reports status `ok`. Every span. 150 times. No errors. No alerts.

Meanwhile it has spent $47 in an infinite retry loop — regenerating the same output, calling the same tool, going nowhere. LangSmith sees green. You see a bill.

AgentWatch sees the loop on span 11.

---

## What existing tools miss

| Capability | LangSmith | Langfuse | AgentWatch |
|------------|-----------|----------|------------|
| Trace visualization | ✅ | ✅ | ✅ |
| Cost tracking | ✅ | ✅ | ✅ |
| Silent failure detection (all-ok loops) | ❌ | ❌ | ✅ |
| Coordination failure attribution (MAST) | ❌ | ❌ | ✅ |
| Cross-layer OS/signal discrepancy | ❌ | ❌ | ✅ |
| Memory integrity (MINJA / SpAIware) | ❌ | ❌ | ✅ |
| Default-deny policy engine | ❌ | ❌ | ✅ |
| Interceptor (halt / quarantine / revoke) | ❌ | ❌ | ✅ |
| HMAC-verified signal origin | ❌ | ❌ | ✅ |

---

## Three proof scenarios

### SC1 — Coordination failure
Orchestrator delegates to parallel workers. Worker B returns `error: conflicting instruction`. AgentWatch attributes the failure to the exact agent, maps it to **MAST Category 2** (inter-agent misalignment), identifies call tree depth, and emits a fix direction.

### SC2 — Silent failure
Agent loops 150 times. All spans `status=ok`. Identical summaries. Zero alerts from conventional tools. AgentWatch detects `infinite_retry_loop`, computes `cost_anomaly_ratio=10.0`, flags before the next trace arrives.

### SC3 — Cross-layer discrepancy
Agent self-reports 1 network call. Sysmon shows 3 TCP connections for the same `process_guid`. Delta=2. Severity=high. The agent lied (or was compromised). AgentWatch catches the gap.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Agent Systems                            │
│          orchestrator → worker-a, worker-b, tools               │
└──────────────────────────────┬──────────────────────────────────┘
                               │ Signals (HMAC-signed, Redis stream)
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                        AgentWatch                               │
│                                                                 │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌───────────────┐  │
│  │ Receiver │  │Discovery │  │  Access  │  │    Policy     │  │
│  │  (HMAC)  │  │ Scanner  │  │  Graph   │  │    Engine     │  │
│  └────┬─────┘  └──────────┘  └──────────┘  └───────────────┘  │
│       │                                                         │
│       ▼                                                         │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌───────────────┐  │
│  │ Content  │  │  Memory  │  │ Chronicle│  │    Verdict    │  │
│  │Inspector │  │Integrity │  │(ClickHse)│  │    Engine     │  │
│  └──────────┘  └──────────┘  └──────────┘  └───────────────┘  │
│                                                                 │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌───────────────┐  │
│  │Behavioral│  │  Coord   │  │ Analyst  │  │  Interceptor  │  │
│  │ Baseline │  │Signatures│  │  (SC1-3) │  │halt/quarantine│  │
│  └──────────┘  └──────────┘  └──────────┘  └───────────────┘  │
│                                                                 │
│  ┌──────────┐  ┌──────────────────────────────────────────┐    │
│  │  Host    │  │              FastAPI                     │    │
│  │Telemetry │  │  /traces  /analyst  /interceptor         │    │
│  │(Sysmon)  │  └──────────────────────────────────────────┘    │
│  └──────────┘                                                   │
└─────────────────────────────────────────────────────────────────┘
```

16 layers. Sequential gates. Each layer must pass before the next builds. See [ARCHITECTURE.md](ARCHITECTURE.md) for full detail.

---

## Quickstart

```bash
# 1. Start infrastructure
docker compose up -d redis clickhouse postgres neo4j

# 2. Install
python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"

# 3. Run all gate tests
make gate-all

# 4. Run proof scenarios
make poc

# 5. Start API
make api
# → http://localhost:8000/docs
```

Full setup guide: [docs/QUICKSTART.md](docs/QUICKSTART.md)

---

## API

```bash
# Health — all infra components
GET /api/v1/health

# Analyst report — SC1 + SC2 + SC3 for any trace
GET /api/v1/analyst/report/{trace_id}

# Silent failures in last N hours
GET /api/v1/analyst/silent-failures?hours=24

# All 19 MAST + infra topology signatures
GET /api/v1/analyst/topology-risks

# Quarantine an agent (logged to Chronicle)
POST /api/v1/interceptor/quarantine
{"agent_id": "worker-b", "reason": "MAST C2 detected", "trigger": "analyst"}

# Trace reconstruction from Chronicle
GET /api/v1/traces/{trace_id}

# Agent verdict history
GET /api/v1/agents/{agent_id}/verdicts
```

Full reference: [docs/API.md](docs/API.md)

---

## Infrastructure

| Component | Purpose | Default |
|-----------|---------|---------|
| Redis | Signal stream (`wt:signals`), interceptor bus, memory events | `:6379` |
| ClickHouse | Chronicle — append-only event store, 90-day TTL | `:8123` |
| PostgreSQL | Behavioral baseline, policy store | `:5433` |
| Neo4j | Access graph — agent trust topology | `:7687` |

---

## Detection capabilities

### Memory Integrity Monitor
- **MINJA** (Memory INJection Attack): detects query-only memory poisoning sequences — bridging query → indication prompt → progressive self-write
- **SpAIware**: cross-session repeat detection — flags content seen in previous sessions appearing in current writes

### Coordination Signatures
14 MAST failure modes from [arXiv:2503.13657](https://arxiv.org/abs/2503.13657) (NeurIPS 2025 Spotlight, Cohen's κ=0.88, 1,642 annotated traces) plus 5 infrastructure patterns:

- **Category 1** (Specification): task misinterpretation, role ambiguity, poor decomposition, duplicate roles, missing termination
- **Category 2** (Inter-agent): handoff breakdown, context loss, conflicting parallel outputs, format mismatch
- **Category 3** (Verification): premature termination, incomplete verification, incorrect logic, missing error recovery, no feedback loop
- **Infra**: infinite retry loop, rate limit cascade, context window overflow, API version drift, framework misuse

### Verdict Engine
3-stage judgment with early exit:
1. **Deterministic** — cost threshold, step count, permission violations
2. **Baseline** — 3σ deviation from per-agent behavioral profile
3. **LLM Judge** — sampled (20%), receives summarized trace only (never raw)

---

## Invariants

These are enforced in code and tested in every gate:

- Chronicle is **append-only**. No UPDATE. No DELETE. Ever.
- Signal origin **HMAC-verified** on every emission, not just first.
- Policy Engine **default-deny**. Must be permitted, not just not forbidden.
- Interceptor logs **every action** to Chronicle. Never silent.
- New agent in **restricted mode** until 50 traces in baseline.
- LLM Judge receives **summarized trace**, never raw spans.

---

## Project structure

```
watchtower/
├── core/           # Signal, Trace, EventType — shape defined once
├── discovery/      # Agent scanner + registry
├── access_graph/   # Permission graph, blast radius
├── policy_engine/  # Default-deny + temporal constraints
├── content_inspection/ # 12-pattern IPI/jailbreak detector
├── receiver/       # HMAC verification
├── memory_monitor/ # MINJA + SpAIware detectors
├── chronicle/      # ClickHouse append-only writer + reader
├── verdict/        # 3-stage verdict engine
├── baseline/       # Per-agent behavioral profiling
├── coord_sigs/     # MAST + infra signature library
├── analyst/        # SC1 attribution, SC2 silent, SC3 cross-layer
├── interceptor/    # Halt, quarantine, revoke
├── host_telemetry/ # Sysmon XML + Falco JSON parsers
└── api/            # FastAPI routers + schemas
```

---

## Citation

```bibtex
@inproceedings{cohen2025mast,
  title={MAST: A Multi-Agent System Taxonomy for LLM Failure Mode Classification},
  author={Cohen et al.},
  booktitle={NeurIPS 2025},
  note={arXiv:2503.13657}
}
```

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) — adding signatures, detectors, and new layers.

## License

MIT
