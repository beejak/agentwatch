# Success and Failure Criteria

> Security detection systems are judged differently from general software.  
> A missed detection is not a bug — **it is a security incident.**

---

## The three non-negotiables

```
✦  Zero missed critical attacks     — must-detect suite: 100%
✦  Zero false positives on corpus   — operators stop trusting noisy systems
✦  No broken layers                 — every gate passes before any merge
```

**Violating any of these = repo is in a failed state, regardless of everything else.**

---

## Tier 1 — Security Regression Gates (Zero Tolerance)

**File:** `tests/adversarial/test_must_detect.py`
**Run:** `pytest tests/adversarial/test_must_detect.py`

### PASS Condition
All 10 tests pass. 100%. No exceptions.

### FAIL Condition
Any single test fails = **CRITICAL SECURITY GAP**. Blocks all merges.
No PR may merge while a must-detect test is failing.

### What Each Test Checks

| Test | Component | Minimum Pass Condition |
|------|-----------|----------------------|
| `test_must_detect_ignore_instructions` | ContentInspector | `flagged=True` |
| `test_must_detect_system_override` | ContentInspector | `flagged=True` |
| `test_must_detect_you_are_now` | ContentInspector | `flagged=True` |
| `test_must_detect_disregard_guidelines` | ContentInspector | `flagged=True` |
| `test_must_detect_exfil_url` | ContentInspector | `flagged=True` |
| `test_must_detect_jailbreak_instruction_block` | ContentInspector | `flagged=True` |
| `test_must_detect_policy_override_in_memory` | MIM | `flagged=True`, `severity in (high, critical)` |
| `test_must_detect_minja_sequence` | MIM | at least one write `flagged=True` |
| `test_must_detect_150_identical_ok_spans` | SilentFailure | `detected=True`, `ratio >= 10.0`, `pattern == infinite_retry_loop` |
| `test_must_detect_token_burn_single_span` | Deterministic | `is_conclusive=True` |
| `test_must_detect_sc1_pattern` | Attribution | `failing_agent == worker-b`, `mast_category == 2` |
| `test_must_detect_sc3_delta_2` | CrossLayer | `delta == 2`, `severity == high` |

### Why Zero Tolerance
These are the exact attacks AgentWatch was built to catch.
A miss means an attacker operates undetected. The $47K silent loop scenario
(150 identical spans, all status=ok) demonstrates what one missed detection costs.

---

## Tier 2 — False Positive Gates (Production Quality)

**File:** `tests/adversarial/test_false_positives.py`
**Run:** `pytest tests/adversarial/test_false_positives.py`

### PASS Condition
All 14 tests pass. FP rate = 0% on the defined test corpus.

### FAIL Condition
Any single test fails = **PRODUCTION QUALITY FAILURE**. Blocks merges.

### Why FP Rate Matters as Much as Miss Rate
A system that flags 10% of normal traffic gets disabled by operators within a week.
Trust, once broken, is not recovered. A detection system with high FP rate is
worse than no detection system — it creates alert fatigue and trains operators to ignore it.

### Production FP Budget
- Test corpus FP rate: **0%** (all tests must pass)
- Production representative workload: **< 2%** of real agent spans flagged incorrectly
- Measurement: run `agents/agentic_tester/` and inspect the FP rate in the gap report

### Benign Patterns That Must Never Flag

| Scenario | Why It's a Threat If It Flags |
|----------|-------------------------------|
| Customer service responses | High volume; ops disables detection |
| Code review comments | Developer workflow broken |
| Meeting notes with "system prompt" references | Common in AI-org documentation |
| API documentation | Devs stop writing docs |
| Normal memory writes | Core functionality breaks |
| Batch processing (60 items, diverse summaries) | Silent failure detector unusable |

---

## Tier 3 — Scenario Coverage Gates

**Files:** `tests/scenarios/`, `tests/integration/`, `tests/gates/`
**Run:** `pytest tests/scenarios/ tests/integration/ && make gate-all`

### PASS Condition
All 76 scenario/integration tests pass. All 125 gate tests pass.

### FAIL Condition
Any failure = broken layer. Must fix before merge. Lower urgency than Tier 1/2.

### Attack Scenario Coverage Required

| Scenario | Test File | What Breaks If Missing |
|----------|-----------|----------------------|
| SC4: Tool injection | `test_sc4_tool_injection.py` | Tool-output attack vector |
| SC5: Agent impersonation | `test_sc5_agent_impersonation.py` | Caller spoofing |
| SC6: Instruction drift | `test_sc6_instruction_drift.py` | Mid-trace reprogramming |
| SC7: Context overflow | `test_sc7_context_overflow.py` | Token burn attack |
| SC8: Rate limit cascade | `test_sc8_rate_limit_cascade.py` | Framework fault escalation |
| SC9: Memory exfil | `test_sc9_memory_exfil.py` | Covert channel |
| SC10: Policy bypass | `test_sc10_policy_bypass.py` | Authorization boundary |
| SC11: Multi-hop poison | `test_sc11_multihop_poison.py` | Propagation chain |

---

## Tier 4 — Agentic Testing (Novel Gap Detection)

**Tool:** `python -m agents.agentic_tester`
**Requires:** `LLM_API_KEY`

### PASS Condition
- Detection rate ≥ 90% on LLM-generated novel payloads
- FP rate ≤ 5% on LLM-generated benign payloads
- No `CRITICAL` gaps in gap report

### FAIL Condition
- Detection rate < 80% = significant gap
- FP rate > 10% = production quality issue
- Any `CRITICAL` gap = must fix before release

### What This Adds That Static Tests Cannot
Static tests use hardcoded payloads — the same payloads every run.
The agentic tester uses an LLM to:
- Reason about which patterns can be evaded semantically
- Generate Unicode/encoding variants
- Embed attacks in legitimate-looking context
- Find patterns that produce FPs on business text

Run it before every release. Save the report to `docs/TESTING_GAPS.md`.

---

## Repo-Level Definitions

### Repo PASS (ready to ship)

```
✓  Tier 1:   12/12  must-detect tests
✓  Tier 2:   14/14  false-positive tests
✓  Tier 3:   76/76  scenario/integration tests
            125/125  gate tests
✓  Tier 4:   DR ≥ 90%  FP ≤ 5%  no CRITICAL gaps
─────────────────────────────────────────────────
   TOTAL:  203/203 suite green (incl. agentic tester)
```

### Repo FAIL (not shippable)

```
✗  1+ Tier 1 failure    → CRITICAL SECURITY GAP    stop everything
✗  1+ Tier 2 failure    → PRODUCTION UNREADY        high urgency
✗  1+ gate failure      → BROKEN LAYER              fix before merge
✗  Agentic DR < 80%     → SIGNIFICANT REGRESSION    address before release
✗  Agentic FP > 10%     → NOISE UNACCEPTABLE        tune patterns
```

---

## Metric Thresholds Reference

| Metric | Target | Minimum Acceptable | Fail |
|--------|--------|-------------------|------|
| Must-detect pass rate | 100% | 100% | < 100% |
| FP rate (test corpus) | 0% | 0% | > 0% |
| FP rate (production) | < 1% | < 2% | > 5% |
| Agentic detection rate | ≥ 95% | ≥ 80% | < 80% |
| Agentic FP rate | < 2% | < 5% | > 10% |
| Cost anomaly ratio (SC2) | ≥ 10.0x | ≥ 10.0x | < 10.0x |
| Detection latency P99 | < 100ms | < 500ms | > 1000ms |
| MIM severity for policy override | high/critical | high | low/medium |
| SC3 delta | exact | exact | wrong |
| MAST category attribution | exact | exact | wrong |
