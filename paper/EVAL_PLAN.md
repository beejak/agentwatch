# Paper 1 — Evaluation Plan (the long pole)

Turns the SC2/SC3 claim into measured evidence. Pairs with `paper/OUTLINE.md`.
Same rigor bar as the firewall corpus: frozen labeled dataset, baselines head-to-head,
held-out split, bootstrap CIs, no tuning on test, report what's missed.

Today `tests/benchmark/test_gap.py` is a *qualitative* "LangSmith can't do this" table.
This plan replaces it with a *quantitative* labeled-dataset comparison.

---

## 1. Claim under test & hypotheses

**Claim:** WatchTower detects silent failures (SC2) and cross-layer discrepancies (SC3)
that self-report/output-level monitoring structurally misses, at an acceptable FP rate.

- **H1 (SC2):** WatchTower recall on injected silent failures ≫ self-report baseline,
  at FP rate < X% on benign distractors.
- **H2 (SC3):** WatchTower recall on injected report-vs-host discrepancies ≫ baseline.
- **H3 (structural blindness):** a self-report-trusting baseline has recall ≈ 0 on SC2/SC3
  *by construction* — this is the core argument, and we show it empirically, not just assert it.

H3 is the paper's spine: the baseline can't win because it never sees the signal.

## 2. Dataset

A **frozen, versioned** set of multi-agent execution traces, each = ordered Signals
(the chronicle span shape) + optional host-telemetry events, with a ground-truth label.

- **Scale (v1 target):** ~600–1000 traces. Stratified: ~⅓ SC2-failure, ~⅓ SC3-discrepancy,
  ~⅓ benign (incl. hard distractors). Enough for tight CIs (cf. firewall n=27 was too small).
- **Splits:** `dev` (~30%, tune thresholds) / `test` (~70%, held-out, reported). Never tune on test.
- **Format:** JSONL — `{trace_id, label, subtype, params, spans:[...], host_events:[...], seed, provenance}`.
- **Generation is seeded & deterministic** → fully reproducible; preserved under `eval/` + a tag.
- **Labels are ground truth by construction** (set at injection time), **independent of any
  detector's thresholds** — so a below-threshold injected loop is still labeled a failure
  (a real miss), and a benign cost spike is labeled benign (a real FP if flagged).

## 3. Failure injection (labeled, detector-independent)

Generalize `agents/synthetic/orchestrator.py` into a parameterized generator.

**SC2 — silent failures (status stays "ok" throughout):**
- `infinite_retry_loop` — same tool call repeated K times (vary K incl. borderline below the
  detector's RETRY_REPEAT_THRESHOLD).
- `entropy_collapse` — outputs degrade to near-identical/low-entropy responses.
- `token_burn` — cost balloons M× expected (vary M across/below the anomaly threshold).

**SC3 — report-vs-host discrepancies:**
- `under_report` — agent reports R network calls; host (`sysmon_sim`) shows R+Δ (vary Δ).
- `hidden_exfil` — agent reports 0 outbound; host shows connections to external host.

**Benign distractors (the precision stress — without these, FP rate is meaningless):**
- retries that *resolve* (legit transient errors), genuinely expensive-but-correct traces,
  legitimate reported bursts of network calls (R reported = R observed, large R),
  partial host telemetry (sampling gaps where host < agent — must NOT fire SC3).

## 4. Baselines (head-to-head, same dataset)

- **B1 — self-report monitor (principled stand-in):** flags a trace iff some span has
  `status != ok`. This is the faithful upper bound of what any self-report-trusting tool
  (LangSmith/Langfuse) can see: it cannot flag all-`ok` silent failures, and has no host
  concept for SC3. Operationalizes H3.
- **B2 — naive cost-threshold monitor:** flags on absolute cost > fixed cutoff. Shows that
  *naive* cost rules either miss (threshold too high) or false-positive on expensive-but-correct
  traces — motivating SC2's *relative* cost-anomaly approach.
- **B3 — real LangSmith (optional, subset):** run a representative subset through actual
  LangSmith for credibility; report alongside B1 as confirmation the stand-in is faithful.

## 5. Detectors under test
WatchTower `analyst.silent.detect_silent_failure` (SC2) and `analyst.cross.check_cross_layer`
(SC3), run over each trace's spans/host events. Thresholds frozen from the `dev` split.

## 6. Metrics & statistics
Per detector × class (SC2, SC3) and on benign:
- recall, precision, F1, FP-rate — **bootstrap 95% CIs**, **≥3 seeds**, **test split only**.
- Headline tables: WatchTower vs B1/B2 recall on SC2 and on SC3 (expect B1 ≈ 0 → H3);
  FP-rate on benign distractors (the honest cost of detection).
- Per-subtype breakdown (which failure shapes are hard) + detection vs. injection magnitude
  curves (K, M, Δ) — shows the operating envelope.

## 7. Train/test hygiene
`EXPECTED_COST_PER_SPAN`, `RETRY_REPEAT_THRESHOLD`, `MIN_SPANS_FOR_LOOP`, SC3 Δ-severity
cutoffs are tuned on `dev` and **frozen** before touching `test`. Document the tuned values.

## 8. Robustness / ablations
- SC2 vs benign expensive-but-correct (precision under cost variance).
- SC2 sensitivity to loop length K and cost ratio M (where does recall fall off?).
- SC3 with partial/absent host telemetry — must degrade gracefully, not false-positive when
  host < agent (sampling), and report "unknown" rather than "clean" when host is absent.

## 9. Threats to validity (state these in the paper)
- **Synthetic realism:** generated traces may not match production agents. Mitigate: ground
  injection in documented failure modes (retry storms, token burn, exfil); if possible fold
  in a small set of *real* agent traces; report synthetic-vs-real as a limitation.
- **Injection circularity:** never inject using the detector's own thresholds; labels are
  structural ground truth. (Spec'd in §2/§3.)
- **Baseline fairness:** B1 is a *generous* stand-in (any status≠ok), so we don't strawman;
  B3 confirms against real LangSmith.

## 10. Build plan (reuse first)
| Piece | Reuse / build |
|---|---|
| trace generator | **generalize** `agents/synthetic/orchestrator.py` (it already does SC1/2/3 single traces) into a seeded multi-trace, parameterized generator |
| host telemetry | reuse `agents/adversarial/sysmon_sim.py` |
| detectors | reuse `analyst/silent.py`, `analyst/cross.py` |
| baselines | **new**: `eval/baselines.py` (B1 self-report, B2 cost-threshold) |
| dataset | **new**: `eval/corpus/traces_v0.1.jsonl` (frozen, seeded) + builder |
| harness | **new**: `eval/harness.py` (mirror the firewall repo's: ablation + bootstrap CIs + preserved results JSON) |
| replace | retire the qualitative `tests/benchmark/test_gap.py` table once quantitative results exist |

## 11. Definition of done (what the paper's §6 needs)
- Frozen dataset (tagged) + reproducible generator.
- Test-split tables: WatchTower vs B1/B2 (and B3 subset) recall on SC2 & SC3 with CIs;
  benign FP-rate; per-subtype + magnitude curves.
- H3 demonstrated: baseline recall ≈ 0 on SC2/SC3.
- All artifacts preserved under `eval/results/` for post-publication scrutiny.

## 12. Honesty guardrails
No tuning on test · report failures/FPs prominently · no "100%" off small n · if the data
contradicts H1/H2, change the claim. (Same principles as the firewall eval.)
