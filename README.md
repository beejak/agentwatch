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

**Security observability and enforcement for multi-agent AI systems.**  
*Intercept at the tool call. Enrich with call-tree context. Propagate taint cross-session.*

[![Python 3.12](https://img.shields.io/badge/python-3.12-3776ab?style=flat-square&logo=python&logoColor=white)](https://www.python.org/downloads/)
[![Tests](https://img.shields.io/badge/tests-17%2F17%20gate%20%7C%20207%20suite-22c55e?style=flat-square)](#testing)
[![License: MIT](https://img.shields.io/badge/license-MIT-f59e0b?style=flat-square)](LICENSE)
[![Paper](https://img.shields.io/badge/paper-WatchTower%202026-b31b1b?style=flat-square)](paper/index.html)
[![ClickHouse](https://img.shields.io/badge/Chronicle-append--only-FFCC01?style=flat-square)](https://clickhouse.com)
[![p99](https://img.shields.io/badge/p99%20latency-0.011ms-00e676?style=flat-square)](#performance)

</div>

---

## What this is

AgentWatch is an **observation-first security framework** for multi-agent AI systems. It does two things that existing tools (LangSmith, Langfuse, Lakera, NeMo Guardrails) don't:

1. **Intercepts at the tool-call level** with semantic context — blocking based on *why* a call was made, not just *what* was called
2. **Propagates taint cross-session** — detecting MINJA-class contagion attacks before the next tool call executes

The research is being prepared for IEEE S&P / USENIX Security submission. See [`paper/`](paper/) for the full paper with interactive charts.

---

## The three attack surfaces

| Surface | Example | Prior Art | WatchTower |
|---------|---------|-----------|------------|
| **Input Corruption** | MINJA query-only memory injection (98.2% success rate) | Content classifiers — no persistence | YAML regex rules + cross-session taint |
| **Capability Abuse** | `send_email` with secrets after `read_secret` | Wire-level block — loses intent | `call_tree_contains` semantic context |
| **Multi-Agent Contagion** | Tainted agent writes memory → clean agent reads → inherits taint | **None published** | Cross-session taint ledger (cavemem) |

**WatchTower is the first published system to address all three.**

---

## Key results

| Metric | Target | Measured |
|--------|--------|---------|
| Known-bad detection (17 cases) | 100% | **100%** |
| p99 hot-path latency | < 10ms | **0.011ms** |
| False positive rate (safe reads) | < 1% | **0%** |
| vs. Distributed Sentinel (106ms) | faster | **9,636×** |
| MINJA taint propagation (Q2) | before next call | **< 1ms** |

---

## The firewall layer

On top of the existing 16-layer WatchTower observability stack, this branch adds a **two-tier enforcement layer** built from composable adapters:

```
agents/adapters/
├── hermes.py       ← hook interceptor (pre_tool_call / pre_gateway_dispatch)
├── cavemem.py      ← taint ledger + trust score (SQLite, cross-session)
├── superpowers.py  ← YAML policy evaluator (deterministic, 0.011ms)
├── graphify.py     ← AST call-context enrichment (>90% cache hit target)
├── ruflo.py        ← BFT consensus swarm (async, off hot-path)
├── agent_mem.py   ← persistent agent memory client (writer provenance)
└── caveman.py      ← UTC token compression (hot-path lean)

policies/
├── exfil_email.yaml      ← block send_email with secrets after read_secret
├── destructive_ops.yaml  ← block rm -rf / shred
└── minja_memory.yaml     ← block instruction-like memory writes
```

### Two-tier enforcement

```
L0  IDENTITY FABRIC      Ed25519 token · delegation chain · MAX_DEPTH=8 · caps
L1  INTERCEPT            hermes pre_tool_call hook
L2  ENRICHMENT           graphify AST path (cached <3ms)
L3  DETERMINISTIC RULES  superpowers YAML DSL — 0.011ms p99        ← HOT PATH
L4  TRUST GATE           cavemem score → route only (never hard-block alone)
L5  ESCALATION ROUTER    ambiguity → ruflo swarm | ALLOW
─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─
L6  ASYNC ANALYSIS       ruflo 3-agent BFT consensus — 5s timeout   ← COLD PATH
L7  BARRIER ENFORCE      task-completion barrier
L8  CHRONICLE            ClickHouse append-only audit
```

### Why `call_tree_contains` matters

Wire-level firewalls see *what* tool was called. WatchTower sees *why*:

```yaml
# exfil_email.yaml
match:
  tool: send_email
  context:
    call_tree_contains: [read_secret]   # semantic: was a secret read first?
  any:
    - arg.body: { matches_secret_pattern: true }
verdict: BLOCK
```

`send_email(to="partner@corp.com")` → **ALLOW**  
`send_email(to="partner@corp.com", body="api_key=sk-...")` after `read_secret` → **BLOCK**

Same endpoint. Different call tree. Different verdict.

### Cross-session taint (MINJA defense)

```
Agent A tainted (level 0.9)  →  writes poisoned memory
Agent B reads (query-only)   →  WatchTower: T_B = 0.9 × ρ = 0.72
0.72 ≥ quarantine threshold 0.7  →  B blocked before its next tool call
```

Formal model: `T(B) := max(T_B, T_A × ρ)` with ρ=0.8 hop decay, λ=0.1/hr time decay.  
Recovery: quarantine expires in ~2.5 hours (P5 — no permanent DoS).

---

## Quickstart

```bash
# 1. Start infrastructure
docker compose up -d redis clickhouse postgres neo4j

# 2. Install
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# 3. Run the known-bad gate (17 cases, zero tolerance)
make gate-firewall

# 4. Run the full 207-case test suite
make test

# 5. Run proof scenarios (Q1 + Q2)
make poc

# 6. Start the API
make api
```

> API docs: **http://localhost:8000/docs**

---

## Known-bad gate (gate_firewall)

17 cases across 3 attack surfaces + fail-safe properties. All must pass. Zero tolerance.

```bash
pytest tests/known_bad/test_firewall_kb.py -v
```

| Range | Surface | Cases |
|-------|---------|-------|
| KB01–KB03 | Input corruption | Direct injection, indirect injection, retrieved doc |
| KB04–KB08 | Capability abuse | Email exfil, rm -rf, cap escalation, delegation depth |
| KB09–KB11 | Contagion | MINJA read taint, message taint, quarantine inheritance |
| KB12–KB16 | Fail-safe | Trust recovery, crash→BLOCK, unauth verdict, cache miss |
| Q1, Q2 | Proof scenarios | Coordination attribution, MINJA end-to-end |
| PB01 | Performance | p99 < 10ms, N=1000 concurrent |

---

## Policy DSL

Human-writable YAML. Zero ML. Deterministic. Hot-reload on session start.

```yaml
rule:    <rule_id>
surface: capability_abuse | input_corruption | contagion
on:      pre_tool_call | pre_gateway_dispatch
match:
  tool: <tool_name>
  any:  [<clause>, ...]     # OR
  all:  [<clause>, ...]     # AND
  context:
    call_tree_contains: [<caller>, ...]   # semantic context
verdict:  BLOCK
severity: 0.0–1.0
reason:   "<string>"
```

**Operators:** `not_in_domain` · `in` · `not_in` · `matches_secret_pattern` · `regex` · `glob` · `rate_exceeds` · `delegation_depth_gt` · `taint_gte`

Full reference: [docs/FIREWALL.md](docs/FIREWALL.md)

---

## Observability stack (existing layers)

The firewall sits on top of the 16-layer observability stack:

| Component | What it does |
|-----------|-------------|
| `watchtower/memory_monitor/` | MINJA + SpAIware detectors, 14 regex patterns |
| `watchtower/coord_sigs/` | 19 MAST + infra coordination failure signatures |
| `watchtower/verdict/` | 3-stage verdict engine (deterministic → baseline → LLM judge) |
| `watchtower/interceptor/` | Halt · quarantine · revoke_memory |
| `watchtower/chronicle/` | ClickHouse append-only event store |
| `watchtower/analyst/` | SC1 attribution · SC2 silent failure · SC3 cross-layer discrepancy |
| `watchtower/baseline/` | Per-agent 3σ behavioral profiling |
| `watchtower/content_inspection/` | 15 IPI/jailbreak/exfil patterns |

---

## Research paper

Full paper with interactive charts: [`paper/index.html`](paper/index.html)

Key sections:
- §2 — Related work: LlamaFirewall, AgentSpec, Distributed Sentinel, Claw Patrol, MINJA
- §4 — 9-layer architecture + semantic rule examples
- §5 — Taint propagation formal model with convergence proof
- §6 — Evaluation: 17/17 results, latency distribution, detection-by-surface comparison
- §7 — Discussion: open problems, limitations

Social preview card: [`paper/card.svg`](paper/card.svg)  
Share copy (LinkedIn / X thread): [`paper/SHARE.md`](paper/SHARE.md)

---

## Project structure

```
agents/
└── adapters/           Firewall adapter layer
    ├── hermes.py       Intercept hooks + two-tier enforcement pipeline
    ├── cavemem.py      Taint ledger + trust score (SQLite + aiosqlite)
    ├── superpowers.py  YAML policy evaluator
    ├── graphify.py     AST enrichment bridge (graphify-ts / tree-sitter)
    ├── ruflo.py        Async BFT consensus swarm
    ├── agent_mem.py   Persistent memory client (cavemem MCP)
    └── caveman.py      UTC token compression

firewall/
└── core/
    └── signal.py       Canonical signal shapes (HookEvent, EnrichedEvent,
                        IdentityCtx, Taint, FirewallVerdict, Verdict)

policies/
├── exfil_email.yaml
├── destructive_ops.yaml
└── minja_memory.yaml

tests/
└── known_bad/
    └── test_firewall_kb.py   17-case gate corpus

paper/
├── index.html          Interactive research paper
├── PAPER.md            Markdown source
├── card.svg            1200×630 social preview card
└── SHARE.md            LinkedIn / X share copy

watchtower/             16-layer observability stack (existing)
docs/                   Full documentation suite
```

---

## Security invariants

```
✦  Chronicle is APPEND-ONLY. No UPDATE. No DELETE. Ever.
✦  Any internal firewall error → BLOCK, never ALLOW (fail-safe default).
✦  Policy Engine is DEFAULT-DENY. Must be permitted, not just not forbidden.
✦  Interceptor logs every action to Chronicle. Never silent.
✦  call_tree_contains is evaluated deterministically — no LLM on hot path.
✦  Taint quarantine expires (λ decay). No permanent DoS.
✦  Async verdict requires matching event_id in hold registry. No spoofing.
```

---

## External tool stack

| Tool | Role | Path |
|------|------|------|
| [hermes-agent](https://github.com/nousresearch/hermes-agent) | Hook intercept runtime | `agents/adapters/hermes.py` |
| [cavemem](https://github.com/JuliusBrussee/cavemem) | Taint + trust persistent store | `agents/adapters/cavemem.py` |
| [superpowers](https://github.com/obra/superpowers) | YAML policy loader | `agents/adapters/superpowers.py` |
| [graphify-ts](https://github.com/Howell5/graphify-ts) | AST call-context (tree-sitter) | `agents/adapters/graphify.py` |
| [ruflo](https://github.com/ruvnet/ruflo) | Async BFT consensus swarm | `agents/adapters/ruflo.py` |
| [caveman](https://github.com/JuliusBrussee/caveman) | UTC token compression | `agents/adapters/caveman.py` |

---

## Infrastructure

| Component | Role | Port |
|-----------|------|------|
| Redis | Signal stream, interceptor bus | 6379 |
| ClickHouse | Chronicle — append-only, 90-day TTL | 8123 |
| PostgreSQL | Behavioral baseline, policy store | 5432 |
| Neo4j | Agent trust topology, blast radius | 7687 |

---

## Citation

```bibtex
@misc{watchtower2026,
  title   = {WatchTower: Observation-First Agent Security —
             Taint Propagation and Semantic Enforcement in Multi-Agent Systems},
  author  = {WatchTower Research},
  year    = {2026},
  note    = {Under submission. Code: https://github.com/beejak/agentwatch}
}

@inproceedings{cohen2025mast,
  title     = {MAST: A Multi-Agent System Taxonomy for LLM Failure Mode Classification},
  author    = {Cohen et al.},
  booktitle = {NeurIPS 2025},
  note      = {arXiv:2503.13657, Spotlight}
}
```

---

## Contributing

[CONTRIBUTING.md](CONTRIBUTING.md) — adding policies, detectors, and new layers.

## License

MIT
