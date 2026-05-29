# MAST Taxonomy

AgentWatch implements the complete MAST failure classification from:

> **MAST: A Multi-Agent System Taxonomy for LLM Failure Mode Classification**  
> NeurIPS 2025 Spotlight · arXiv:[2503.13657](https://arxiv.org/abs/2503.13657)  
> Cohen's κ = **0.88** inter-rater agreement · **1,642** annotated production traces

---

## Why this matters

Before MAST, "my agent failed" was the entire diagnosis.

MAST provides a shared vocabulary for failure modes with empirical frequency data from real production systems. AgentWatch operationalizes the taxonomy — moving it from a research paper into live detection with automated attribution and fix directions.

---

## Frequency distribution

```
Category 1 — Specification     ████████████████████░░░░░░░░   41.8%
Category 2 — Inter-agent        ████████████████░░░░░░░░░░░░   36.9%
Category 3 — Verification       █████████░░░░░░░░░░░░░░░░░░░   21.3%
```

---

## Category 1 — Specification Failures (41.8%)

> The agent does what it was told — but what it was told is wrong.

| ID | Signature | Risk | Detection signals |
|----|-----------|------|-------------------|
| `mast_c1_task_misinterpretation` | Task Misinterpretation | high | Output unrelated to input; high step count with wrong direction |
| `mast_c1_role_ambiguity` | Role Ambiguity | medium | Duplicate tool calls across agents; conflicting outputs in same domain |
| `mast_c1_poor_decomposition` | Poor Task Decomposition | high | Circular dependencies in handoffs; subtask failure cascade |
| `mast_c1_duplicate_roles` | Duplicate Agent Roles | medium | Same tool called by multiple agents; identical output summaries |
| `mast_c1_missing_termination` | **Missing Termination Condition** | **CRITICAL** | Span count >50; same action repeated >5×; cost anomaly ratio >10 |

> **Missing Termination Condition** is the most expensive failure in practice — it's the silent loop pattern (SC2). 150 spans × $0.00045 = $0.07 per run. 1,000 agents × 100 runs/day = **$7,000/day**.

---

## Category 2 — Inter-Agent Misalignment (36.9%)

> Individual agents work correctly. Their interaction doesn't.

| ID | Signature | Risk | Detection signals |
|----|-----------|------|-------------------|
| `mast_c2_handoff_breakdown` | Handoff Breakdown | high | Caller output not in callee context; instruction hash mismatch |
| `mast_c2_context_loss` | Context Loss Between Agents | high | Reference to prior step missing; repeated information gathering |
| `mast_c2_conflicting_parallel_outputs` | **Conflicting Parallel Outputs** | **CRITICAL** | Multiple agents, same parent span; ≥1 worker `status=error` |
| `mast_c2_format_mismatch` | Format Mismatch | medium | Parsing error in callee; tool execution failure at handoff |

> **Conflicting Parallel Outputs** is SC1. Workers produce mutually exclusive results. The orchestrator has no conflict resolution strategy. AgentWatch attributes it to the exact failing agent with MAST category.

---

## Category 3 — Verification Gaps (21.3%)

> The task completes — but incorrectly. No one checked.

| ID | Signature | Risk | Detection signals |
|----|-----------|------|-------------------|
| `mast_c3_premature_termination` | Premature Termination | high | Task marked complete but output empty; subsequent agent finds work remaining |
| `mast_c3_incomplete_verification` | Incomplete Verification | high | Verification step <10ms; no verification span in trace |
| `mast_c3_incorrect_verification_logic` | Incorrect Verification Logic | high | Verdict passes but output reverted; indirect signal negative after pass |
| `mast_c3_missing_error_recovery` | Missing Error Recovery | medium | `error` status followed by `ok` without retry span |
| `mast_c3_no_feedback_loop` | No Feedback Loop | medium | Sequential chain depth >3; no parent span references downstream |

---

## Infrastructure Patterns (AgentWatch additions)

5 patterns beyond MAST covering infrastructure failure modes:

| ID | Signature | Risk | Description |
|----|-----------|------|-------------|
| `infra_infinite_retry_loop` | **Infinite Retry Loop** | **CRITICAL** | HTTP 200, no errors, wrong and expensive |
| `infra_rate_limit_cascade` | Rate Limit Cascade | high | Rate limit triggers exponential backoff cascade across agents |
| `infra_context_window_overflow` | Context Window Overflow | high | Agent accumulates context exceeding model limit |
| `infra_api_version_drift` | API Version Drift | medium | Agent uses deprecated API; unexpected behavior |
| `infra_framework_api_misuse` | Framework API Misuse | medium | Framework used incorrectly causing silent failures |

---

## How matching works

For each incoming trace:

```
1. Extract span graph
   agents · actions · parent/child relationships · statuses

2. For each signature
   check detection_signals against extracted features

3. Score match (0.0 – 1.0)
   confidence proportional to signal specificity

4. Return ranked matches above threshold
   with fix_direction attached
```

**Example — `mast_c2_conflicting_parallel_outputs` detection signals:**

```yaml
detection_signals:
  - multiple_agents_same_parent_span    # ≥2 agents with same parent_span_id
  - one_or_more_worker_status_error     # at least one span has status=error
  - parallel_workers_gt_1              # more than 1 unique agent_id at same depth
```

All three present → match.

---

## Fix directions

Every signature includes a prescriptive fix direction returned directly in analyst reports:

| Category | Fix directions |
|----------|----------------|
| **C1 — Specification** | Clarify task spec · add explicit success criteria · define termination condition · assign clear ownership |
| **C2 — Inter-agent** | Explicit context passing · structured handoff schema · add consensus/merge step · typed interface contracts |
| **C3 — Verification** | Add completion verification step · comprehensive checklist · error handling and retry logic · reflection step |

---

## Citation

```bibtex
@inproceedings{cohen2025mast,
  title     = {MAST: A Multi-Agent System Taxonomy for LLM Failure Mode Classification},
  author    = {Cohen et al.},
  booktitle = {Advances in Neural Information Processing Systems},
  year      = {2025},
  note      = {Spotlight. arXiv:2503.13657}
}
```
