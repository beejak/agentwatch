# Testing & Quality Report — WatchTower (agentwatch)

Snapshot of what's tested and how, kept honest. Regenerate counts with `make test`.

## Headline
- **203 tests passing**, 0 warnings.
- **84% line coverage** overall (`--cov=watchtower`); core modules 90–100%.
- **CI-gated on every push/PR**: full suite + per-layer gate matrix, against live
  Redis / ClickHouse / Postgres / Neo4j service containers.
- Deterministic — no flaky tests; no network/LLM dependency in the suite.

## Test inventory (203 across 31 files)

| Area | Tests | What it verifies |
|------|------:|------------------|
| `tests/gates/` | 112 | One acceptance gate per layer (01–16): core, discovery, receiver, content-inspection, memory-monitor, chronicle, verdict, baseline, coord-sigs, analyst, interceptor, api, host-telemetry |
| `tests/scenarios/` | 46 | End-to-end attack/behaviour scenarios |
| `tests/adversarial/` | 24 | Adversarial trace generation + detection |
| `tests/poc/` | 12 | Proof scenarios — **SC1** coordination-failure attribution, **SC2** silent failure, **SC3** cross-layer discrepancy |
| `tests/unit/` | 5 | Pure-unit tests (verdict baseline-deviation source) |
| `tests/eval/` | 3 | Observability eval harness sanity (corpus integrity, **H3**: self-report baseline blindness) |
| `tests/benchmark/` | 1 | WatchTower vs. LangSmith capability-gap |

## How to run
```bash
make gate-all      # every layer gate, gate-first (stop on first failure)
make test          # full suite (203) with coverage
make poc           # SC1 + SC2 + SC3 proof scenarios
make benchmark     # LangSmith gap comparison
python -m eval.harness          # SC2/SC3 detection vs baselines (held-out metrics)
```
Infra: `docker compose up -d redis clickhouse postgres neo4j` (a rootless single-binary
ClickHouse suffices for the chronicle tests if Docker is unavailable).

## Coverage detail (honest)
- **90–100%**: core, discovery, content-inspection, memory-monitor, chronicle, verdict
  engine, policy engine, coord-sigs, analyst, interceptor, host-telemetry correlator.
- **`verdict/sources/baseline.py` → 100%** (was 27%; closed with unit tests).
- **Lower, by design / nature:**
  - `receiver/receiver.py` 54% — the *live async ingestion loop*, exercised via
    integration rather than units.
  - `host_telemetry/falco.py` / `sysmon.py` 54–64% — the **stub** telemetry layers.

## CI
`.github/workflows/ci.yml` runs `make gate-all` then `make test` (full suite + coverage)
on every push and PR, with all four service containers. `.github/workflows/gate-check.yml`
runs each layer gate as a parallel matrix on PRs touching code/tests.

## Maturity scorecard (why this is "pristine")
| Criterion | Status |
|-----------|--------|
| CI runs the full suite, green | ✅ |
| Coverage at a sensible floor, gaps filled | ✅ 84%, core 90–100% |
| Known bugs fixed | ✅ pattern recompile-per-call → compile-once |
| Deprecations cleared | ✅ FastAPI `lifespan`; pytest-asyncio loop scope |
| No flaky/nondeterministic tests | ✅ 203 repeatable |
| Single clean source of truth | ✅ |

Enforcement (the firewall) is a separate repo —
**[agentwatch-firewall](https://github.com/beejak/agentwatch-firewall)** — with its own tests.
