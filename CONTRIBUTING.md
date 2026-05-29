# Contributing

## What to contribute

- **New coordination signatures** — add MAST or infra patterns to the YAML library
- **New detectors** — extend MIM, content inspection, or verdict engine
- **New proof scenarios** — document a real failure mode with a reproducible test
- **Connector agents** — emit signals from LangChain, CrewAI, AutoGen, etc.
- **Host telemetry parsers** — Falco rules, auditd, eBPF integrations

---

## Development setup

```bash
git clone https://github.com/agentwatch/agentwatch.git
cd agentwatch
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
docker compose up -d redis clickhouse postgres neo4j
make gate-all   # all 125 tests must pass before you start
```

---

## Adding a coordination signature

Signatures live in `watchtower/coord_sigs/signatures/`.

**Add to `mast.yaml` or `infra.yaml`:**

```yaml
category_2_inter_agent_misalignment:
  signatures:
    - id: mast_c2_your_new_pattern
      name: "Your Pattern Name"
      risk_level: high          # critical / high / medium / low
      description: "One sentence describing the failure mode"
      detection_signals:
        - signal_one            # matched against span graph features
        - signal_two
      fix_direction: "Actionable recommendation for fixing this pattern"
```

**Supported detection signals:**

| Signal | Meaning |
|--------|---------|
| `multiple_agents_same_parent_span` | ≥2 agents share a parent span |
| `one_or_more_worker_status_error` | At least one span has status=error |
| `parallel_workers_gt_1` | Multiple workers at same depth |
| `span_count_exceeds_50` | More than 50 spans in trace |
| `same_action_repeated_gt_5_times` | Same action >5 times |
| `cost_anomaly_ratio_gt_10` | Cost >10x baseline |
| `instruction_hash_mismatch` | instruction_hash changed between spans |
| `circular_dependencies_in_handoffs` | Cycle in parent_span_id graph |

Add new signals by extending `watchtower/coord_sigs/matcher.py`.

**Write a gate test:**

```python
# tests/gates/gate_11_coord.py (add to existing)
def test_your_new_signature(coord_library):
    spans = [...]   # craft spans that trigger your signal
    matches = asyncio.run(coord_library.match_topology(spans))
    names = [m.name for m in matches]
    assert "Your Pattern Name" in names
```

---

## Adding a content inspection pattern

Patterns in `watchtower/content_inspection/patterns/injection_patterns.yaml`:

```yaml
patterns:
  - id: your_pattern_id
    name: "Pattern Display Name"
    pattern: "regex_pattern_here"
    severity: high
    description: "What this catches"
```

The inspector compiles all patterns at startup. Test:

```python
from watchtower.content_inspection.inspector import ContentInspector

inspector = ContentInspector()
result = inspector.inspect("your test content here")
assert result.flagged
assert result.pattern_matched == "your_pattern_id"
```

---

## Adding a new detector to MIM

Detectors in `watchtower/memory_monitor/detectors/`:

```python
# watchtower/memory_monitor/detectors/your_detector.py

def detect_your_pattern(history: list[dict]) -> bool:
    """
    Returns True if the agent history matches your attack pattern.
    history: list of {"operation": "read"|"write", "content": str}
    """
    ...
```

Wire it into `MemoryIntegrityMonitor.on_write()` in `monitor.py`.

---

## Gate-driven development

Every layer has a gate test. The gate must pass before the next layer starts. This is enforced by `make gate-all` which stops on first failure.

When adding a new feature:
1. Write the gate test first
2. Run `make gate-NN` — it should fail
3. Implement the feature
4. Run `make gate-NN` — it should pass
5. Run `make gate-all` — all 125 tests must still pass

---

## Invariants you must not break

These are non-negotiable:

1. **Chronicle is append-only.** Never issue UPDATE or DELETE against any Chronicle table.
2. **Signal shape is defined once.** Do not add fields to Signal in any file other than `watchtower/core/signal.py`.
3. **All I/O is async.** No `requests`, no `psycopg2`, no synchronous DB calls.
4. **Policy engine is default-deny.** A missing policy rule means DENY, not ALLOW.
5. **Interceptor always logs.** Chronicle write must complete before `InterceptorAction` is returned.

---

## PR checklist

- [ ] `make gate-all` passes (125 tests)
- [ ] New feature has a gate test
- [ ] No sync I/O introduced
- [ ] No Chronicle UPDATE/DELETE
- [ ] Signal shape unchanged (unless adding to `core/signal.py` with gate test)
- [ ] SPEC.md §T updated if a new layer was added
- [ ] SPEC.md §B updated if a bug was fixed
