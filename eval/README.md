# WatchTower Observability Evaluation (Paper 1)

Quantitative evidence for the SC2/SC3 claim (see `paper/OUTLINE.md`, `paper/EVAL_PLAN.md`).
Frozen, human-designed labeled trace corpus → WatchTower detectors vs. baselines →
precision/recall/F1/FP-rate with bootstrap 95% CIs on a **held-out** split. Results are
preserved under `eval/results/` for reproducibility.

## Run
```bash
python -m eval.harness                  # held-out test split
python -m eval.corpus._build_traces_v0_1   # regenerate the frozen corpus (seeded)
```

## Corpus (`corpus/traces_v0.1.jsonl`, 380 traces)
Seeded, reproducible, labeled at generation time **independently of detector thresholds**.
- `silent_failure` (120): retry-loop, token-burn, entropy-collapse — incl. *borderline* cases
  below detector thresholds (→ honest misses).
- `cross_layer` (120): under-report, hidden-exfil (host observes more than the agent reports).
- `benign` (140): normal, retries-that-resolve, **expensive-but-correct**, reported bursts,
  host-sampling gaps (host < agent) — the precision stress.
- Split: `dev` (111, tunable) / `test` (269, **held-out**, reported).

## Baselines
- **B1 self-report** (LangSmith-style): flags only an explicit `status=="error"` span — the
  faithful upper bound of any monitor that trusts the agent's self-report.
- **B2 naive cost**: flags total cost > $0.10.

## Results — held-out `test` (n=269: silent 85, cross 84, benign 100)

### SC2 — silent failure
| detector | precision | recall | F1 | FPR |
|---|---|---|---|---|
| **watchtower** | 0.85 | **0.86** | 0.85 | 0.07 |
| self-report (B1) | 0.00 | **0.00** | 0.00 | 0.00 |
| naive-cost (B2) | 0.64 | 0.27 | 0.38 | 0.07 |

### SC3 — cross-layer discrepancy
| detector | precision | recall | F1 | FPR |
|---|---|---|---|---|
| **watchtower** | 1.00 | **1.00** | 1.00 | 0.00 |
| self-report (B1) | 0.00 | **0.00** | 0.00 | 0.00 |

**The headline is H3, and it's structural:** the self-report baseline scores **0 recall** on
both — it never sees the signal. WatchTower also beats naive cost on SC2 (loop/entropy catch
failures pure-cost misses; pure cost false-positives on expensive-but-correct work).

## ⚠️ Caveats — read before citing

- **Synthetic corpus.** Traces are generated, not production. The *robust* result is the
  **baseline gap (H3)** — structural, holds regardless of realism. Absolute WatchTower numbers
  will move on real traffic; treat them as an upper-ish bound under clean conditions.
- **SC3's 1.00 is partly an artifact.** Synthetic host events attribute to spans perfectly by
  `process_guid`; real host↔agent attribution is noisy (sampling, PID reuse, containers).
  **Do not claim "100% cross-layer detection."** Expect materially lower on real telemetry.
- **SC2 0.86 is the honest number** — it misses borderline injected cases by design (loops
  below the length threshold, token-burn below the cost threshold) and false-positives on some
  expensive-but-correct traces (FPR 0.07). That's the real operating point, not a tuned 1.0.
- **Thresholds are the detectors' module defaults**, not yet tuned on `dev`. Tuning + a
  detection-vs-magnitude sweep is future work.
- **n and independence.** 269 held-out beats the firewall corpus (27) but still needs scaling
  toward 1000s, ideally with *real* agent traces and labels independent of this generator.

## Next (to reach publication-grade)
Scale + inject real traces; tune thresholds on `dev` only; add a real-LangSmith subset (B3) to
confirm B1 is faithful; detection-vs-magnitude curves; report across ≥3 seeds.
