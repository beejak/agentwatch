# MAST Taxonomy

AgentWatch implements the full MAST (Multi-Agent System Taxonomy) failure classification from:

> **MAST: A Multi-Agent System Taxonomy for LLM Failure Mode Classification**  
> NeurIPS 2025 Spotlight  
> arXiv:[2503.13657](https://arxiv.org/abs/2503.13657)  
> Cohen's κ = 0.88 inter-rater agreement  
> 1,642 annotated production traces

---

## Why this matters

Before MAST, "my agent failed" was the entire diagnosis. MAST provides:
- A shared vocabulary for failure modes
- Empirical frequency data from production systems
- Actionable fix directions per category

AgentWatch operationalizes the taxonomy — moving it from a research paper into live detection.

---

## Category 1 — Specification Failures (41.8%)

Failures rooted in how the task or agent is designed. The agent does what it was told — but what it was told is wrong.

| ID | Name | Risk | Detection signals |
|----|------|------|-------------------|
| `mast_c1_task_misinterpretation` | Task Misinterpretation | high | Output unrelated to input; high step count with wrong direction |
| `mast_c1_role_ambiguity` | Role Ambiguity | medium | Duplicate tool calls across agents; conflicting outputs in same domain |
| `mast_c1_poor_decomposition` | Poor Task Decomposition | high | Circular dependencies in handoffs; subtask failure cascade |
| `mast_c1_duplicate_roles` | Duplicate Agent Roles | medium | Same tool called by multiple agents; identical output summaries |
| `mast_c1_missing_termination` | **Missing Termination Condition** | **critical** | Span count >50; same action repeated >5 times; cost anomaly ratio >10 |

**Missing Termination Condition** is the most expensive failure in practice — it's the infinite loop pattern (SC2).

---

## Category 2 — Inter-Agent Misalignment (36.9%)

Failures in how agents communicate and coordinate. Individual agents work correctly; their interaction doesn't.

| ID | Name | Risk | Detection signals |
|----|------|------|-------------------|
| `mast_c2_handoff_breakdown` | Handoff Breakdown | high | Caller output not in callee context; instruction hash mismatch |
| `mast_c2_context_loss` | Context Loss Between Agents | high | Reference to prior step missing; repeated information gathering |
| `mast_c2_conflicting_parallel_outputs` | **Conflicting Parallel Outputs** | **critical** | Multiple agents, same parent span; ≥1 worker status=error; parallel workers >1 |
| `mast_c2_format_mismatch` | Format Mismatch | medium | Parsing error in callee; tool execution failure at handoff |

**Conflicting Parallel Outputs** is SC1 — the scenario where workers produce mutually exclusive results and the orchestrator has no conflict resolution strategy.

---

## Category 3 — Verification Gaps (21.3%)

Failures in how agents validate their own output. The task completes — but incorrectly.

| ID | Name | Risk | Detection signals |
|----|------|------|-------------------|
| `mast_c3_premature_termination` | Premature Termination | high | Task marked complete but output empty; subsequent agent finds work remaining |
| `mast_c3_incomplete_verification` | Incomplete Verification | high | Verification step duration <10ms; no verification span in trace |
| `mast_c3_incorrect_verification_logic` | Incorrect Verification Logic | high | Verdict passes but output reverted; indirect signal negative after pass |
| `mast_c3_missing_error_recovery` | Missing Error Recovery | medium | Error status followed by ok without retry; downstream agent receives error output |
| `mast_c3_no_feedback_loop` | No Feedback Loop | medium | Sequential chain depth >3; no parent span references downstream |

---

## Infrastructure Patterns (AgentWatch additions)

5 patterns added beyond MAST to cover common infrastructure failure modes:

| ID | Name | Risk | Description |
|----|------|------|-------------|
| `infra_infinite_retry_loop` | **Infinite Retry Loop** | **critical** | Agent in retry loop — HTTP 200, no errors, but wrong and expensive |
| `infra_rate_limit_cascade` | Rate Limit Cascade | high | Rate limit hit triggers exponential backoff cascade across agents |
| `infra_context_window_overflow` | Context Window Overflow | high | Agent accumulates context exceeding model limit |
| `infra_api_version_drift` | API Version Drift | medium | Agent uses deprecated API version causing unexpected behavior |
| `infra_framework_api_misuse` | Framework API Misuse | medium | Agent framework used incorrectly causing silent failures |

---

## How matching works

For each incoming trace, AgentWatch runs topology matching:

1. Extract span graph: agents, actions, parent/child relationships, statuses
2. For each signature: check detection signals against extracted features
3. Score each match (0.0–1.0)
4. Return ranked matches above threshold

**Example: `mast_c2_conflicting_parallel_outputs` detection signals:**
```yaml
detection_signals:
  - multiple_agents_same_parent_span    # ≥2 agents with same parent_span_id
  - one_or_more_worker_status_error     # at least one span has status=error
  - parallel_workers_gt_1              # more than 1 unique agent_id at same depth
```

All three signals present → match. Confidence proportional to specificity of match.

---

## Fix directions

Every MAST signature includes a prescriptive fix direction:

| Category | Common fix directions |
|----------|-----------------------|
| C1 Specification | Clarify task spec; add explicit success criteria; define termination condition; assign clear ownership |
| C2 Inter-agent | Explicit context passing; structured handoff schema; add consensus/merge step; typed interface contracts |
| C3 Verification | Add completion verification step; comprehensive verification checklist; add error handling and retry logic; add reflection step |

These are returned directly in analyst reports — actionable without additional interpretation.

---

## Citation

```bibtex
@inproceedings{cohen2025mast,
  title={MAST: A Multi-Agent System Taxonomy for LLM Failure Mode Classification},
  author={Cohen et al.},
  booktitle={Advances in Neural Information Processing Systems},
  year={2025},
  note={Spotlight. arXiv:2503.13657}
}
```
