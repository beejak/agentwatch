# Paper 1 — WatchTower (observability) — Scoping Doc

**Status:** scoping / pre-draft. This is the spine we agree on *before* writing prose.
**Scope split:** enforcement (firewall, policy DSL, cross-session taint/MTP, semantic
verdicts) is **Paper 2** (lives in `agentwatch-firewall`). This paper is observability
only and ships first.

---

## 1. Core claim (one sentence)

> An AI agent's self-report is not ground truth: output- and trace-level monitoring
> trust what the agent says it did, leaving two structural blind spots —
> **success-shaped failures** and **report-vs-reality gaps** — that WatchTower detects
> by cross-checking the execution *trajectory* and the *host* layer.

## 2. The problem (why it matters)

Existing agent monitors (LangSmith, Langfuse) record what the agent emits. But:
- **SC2 — silent failures:** an agent can report `status=ok` on every span while stuck
  in a retry loop, collapsing in output entropy, or burning tokens — a failure that is
  *invisible at the output level* (the "$47k" failure: 150 green spans, no error).
- **SC3 — cross-layer discrepancy:** the agent's reported actions need not match what the
  host actually did. Trace says "1 api_call"; host telemetry (Sysmon/Falco) shows 4
  outbound connections → 3 unreported calls (exfil / injected code / tampering).

Both are invisible to anything that trusts the agent's self-report. This is a *security*
problem, not just a reliability one: SC3 is an evasion/exfil signal.

## 3. Thesis & insight

Monitoring that consumes only the agent's self-report inherits the agent's blind spots
and lies. The fix is **observation-first, multi-layer reconciliation**: compare the
self-report against (a) the *shape* of the trajectory (cost/loop/entropy) and (b) an
independent *host* ground truth. Discrepancy is the signal.

## 4. Contributions (claims we must defend)

- **C1 (SC2): success-shaped failure detection.** Cost-anomaly ratio + retry-loop +
  entropy-collapse detectors flag failures that never raise an error.
- **C2 (SC3): cross-layer reconciliation.** Reconcile agent-reported network/tool actions
  against host telemetry; quantify the delta as a tamper/exfil severity.
- **C3 (substrate): append-only forensic Chronicle + attribution.** A no-UPDATE/no-DELETE
  event store that supports post-hoc attribution of a coordination failure to
  agent + action + call-tree position (SC1) — the forensic payoff that makes C1/C2
  actionable. *(SC1 is supporting, not the headline.)*

## 5. Related work — positioning

| Line | What they do | Gap we fill |
|------|--------------|-------------|
| LangSmith / Langfuse | trace/output logging of agent self-report | trust the self-report; no host cross-check; no success-shaped-failure detector |
| "Agentic AI Process Observability" (2505.20127) | process-mining of trajectories | stochastic-trajectory framing; not a security/discrepancy detector |
| "The Observability Gap" (2603.26942) | argues output-level feedback insufficient | we *operationalize* it: concrete SC2/SC3 detectors + evaluation |
| Host EDR (Sysmon/Falco) | host events, no agent semantics | we bridge host events to agent trajectory (SC3) |

Novelty hook: **the reconciliation across self-report ↔ trajectory ↔ host** as a security
signal, with concrete detectors and a forensic substrate.

## 6. Failure/threat model (sketch)

- Agents may report success while failing (non-adversarial bugs *and* adversarial masking).
- A compromised/injected agent may under-report its actions (SC3 exfil).
- Out of scope (→ Paper 2): enforcement/blocking, prompt-injection content detection,
  cross-session taint. This paper *observes and attributes*; it does not act.

## 7. Evidence — HAVE vs NEED

**Have (capability demonstrations, not yet an evaluation):**
- `tests/poc/scenario_02_silent.py`, `scenario_03_crosslayer.py`, `scenario_01_coordination.py`
- `analyst/silent.py`, `analyst/cross.py`, `analyst/attribution.py`
- LangSmith comparison harness (`tests/benchmark/`); append-only Chronicle (ClickHouse)
- 195-test suite; 16-layer build

**Need (the real evaluation — same rigor bar as the firewall corpus):**
1. A **realistic multi-agent workload + failure dataset** (mix of silent failures, exfil/
   under-reporting, and benign traces) — labeled independently of WatchTower.
2. **Baselines head-to-head**: output-level monitoring (LangSmith-style) vs WatchTower on
   the same dataset. Headline metric: *"detects N% of silent failures / discrepancies the
   baseline structurally misses, at FP rate X%."*
3. **Held-out split + bootstrap CIs**; ≥2 seeds. No tuning on the test set.
4. SC2 robustness: cost-anomaly thresholds must generalize (don't hand-fit to the demo).
5. SC3 requires host telemetry — characterize availability/overhead; what happens when it's
   absent (graceful degradation).

## 8. Proposed section structure

1. Intro — the self-report-is-not-ground-truth problem; the "$47k" + exfil motivating cases
2. Background & related work — output/trace monitors, observability-gap arguments, host EDR
3. Failure & threat model
4. Design — Chronicle substrate; SC2 detectors; SC3 reconciliation; SC1 attribution
5. Implementation — 16 layers, async, append-only, host-telemetry correlation
6. Evaluation — dataset, baselines, SC2/SC3 detection vs baseline, CIs, ablations
7. Discussion — limits (host-telemetry dependence, threshold calibration), Paper-2 teaser
8. Conclusion

## 9. Risks / open questions (be honest in the paper)

- SC1 attribution alone is incremental — keep it supporting, lead with SC2/SC3.
- "Observability" is crowded; the defensible novelty is **multi-layer reconciliation as a
  security signal**, so the evaluation must *quantify what baselines miss* — capability
  demos won't pass review.
- Need a credible, ideally public-ish, multi-agent failure dataset; building one is the
  critical-path work.
- SC2 cost-based detection could be gamed/spurious; needs robustness analysis.

## 10. Immediate next steps

1. Agree the core claim (§1) and contributions (§4).
2. Move the current firewall-centric `paper/PAPER.md` content to `agentwatch-firewall`
   as the Paper-2 base; reset this repo's `paper/` to the Paper-1 outline.
3. Spec the evaluation dataset (§7) — this is the long pole.
