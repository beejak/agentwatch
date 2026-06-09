"""
eval/harness.py — WatchTower observability evaluation (SC2/SC3) against the frozen
labeled trace corpus. Reports precision/recall/F1/FP-rate with bootstrap 95% CIs on
a held-out split, and writes preserved JSON artifacts to eval/results/.

Two panels (each: WatchTower vs. baselines on the held-out test split):
  SC2 silent failure   — positive class = label "silent_failure"
                         WatchTower = analyst.silent.detect_silent_failure().detected
                         B1 self-report = any span status == "error"   (LangSmith-style)
                         B2 naive cost  = total cost > $0.10
  SC3 cross-layer      — positive class = label "cross_layer"
                         WatchTower = analyst.cross.check_cross_layer().delta > 0
                         B1 self-report = any span status == "error"   (no host concept)

H3 (structural blindness): the self-report baseline cannot see all-"ok" silent
failures or host-vs-report gaps, so its recall ≈ 0 on both panels — by construction.

Usage:
  python -m eval.harness                 # held-out test split
  python -m eval.harness --split all
  python -m eval.harness --out eval/results/run.json
"""
from __future__ import annotations

import argparse
import asyncio
import json
import random
import time
from pathlib import Path

CORPUS = Path(__file__).parent / "corpus" / "traces_v0.1.jsonl"
RESULTS_DIR = Path(__file__).parent / "results"
BOOTSTRAP_B = 2000
BOOTSTRAP_SEED = 1729


def load_corpus(split: str = "test") -> list[dict]:
    recs = [json.loads(l) for l in CORPUS.read_text().splitlines() if l.strip()]
    return recs if split == "all" else [r for r in recs if r["split"] == split]


# ── baselines ────────────────────────────────────────────────────────────────
def b1_self_report(trace: dict) -> bool:
    """LangSmith-style: trusts the agent; only an explicit error span is visible."""
    return any(s.get("status") == "error" for s in trace["spans"])


def b2_naive_cost(trace: dict) -> bool:
    return sum(s.get("cost", 0.0) or 0.0 for s in trace["spans"]) > 0.10


# ── metrics ──────────────────────────────────────────────────────────────────
def _confusion(pairs):
    tp = sum(1 for y, p in pairs if y and p)
    fp = sum(1 for y, p in pairs if not y and p)
    fn = sum(1 for y, p in pairs if y and not p)
    tn = sum(1 for y, p in pairs if not y and not p)
    return {"tp": tp, "fp": fp, "fn": fn, "tn": tn}


def _prf(c):
    tp, fp, fn, tn = c["tp"], c["fp"], c["fn"], c["tn"]
    p = tp / (tp + fp) if (tp + fp) else 0.0
    r = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * p * r / (p + r) if (p + r) else 0.0
    fpr = fp / (fp + tn) if (fp + tn) else 0.0
    return {"precision": p, "recall": r, "f1": f1, "fpr": fpr}


def _bootstrap_ci(pairs, metric):
    if not pairs:
        return [0.0, 0.0]
    rng = random.Random(BOOTSTRAP_SEED)
    n = len(pairs)
    vals = sorted(_prf(_confusion([pairs[rng.randrange(n)] for _ in range(n)]))[metric]
                  for _ in range(BOOTSTRAP_B))
    return [round(vals[int(0.025 * BOOTSTRAP_B)], 3), round(vals[int(0.975 * BOOTSTRAP_B)], 3)]


def _panel(labels, preds_by_detector):
    out = {}
    for name, preds in preds_by_detector.items():
        pairs = list(zip(labels, preds))
        conf = _confusion(pairs)
        out[name] = {**conf, **{k: round(v, 3) for k, v in _prf(conf).items()},
                     "recall_ci95": _bootstrap_ci(pairs, "recall"),
                     "f1_ci95": _bootstrap_ci(pairs, "f1")}
    return out


async def run_eval(split: str = "test") -> dict:
    from watchtower.analyst.silent import detect_silent_failure
    from watchtower.analyst.cross import check_cross_layer

    traces = load_corpus(split)
    y_sc2, y_sc3 = [], []
    wt_sc2, wt_sc3, b1, b2 = [], [], [], []
    for t in traces:
        y_sc2.append(t["label"] == "silent_failure")
        y_sc3.append(t["label"] == "cross_layer")
        wt_sc2.append((await detect_silent_failure(t["trace_id"], t["spans"])).detected)
        wt_sc3.append((await check_cross_layer(t["trace_id"], t["spans"], t.get("host_events"))).delta > 0)
        b1.append(b1_self_report(t))
        b2.append(b2_naive_cost(t))

    return {
        "corpus": "traces_v0.1", "split": split, "n_traces": len(traces),
        "n_silent": sum(y_sc2), "n_cross": sum(y_sc3),
        "n_benign": sum(1 for t in traces if t["label"] == "benign"),
        "bootstrap_B": BOOTSTRAP_B,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "panels": {
            "SC2_silent_failure": _panel(y_sc2, {
                "watchtower": wt_sc2, "self_report_B1": b1, "naive_cost_B2": b2}),
            "SC3_cross_layer": _panel(y_sc3, {
                "watchtower": wt_sc3, "self_report_B1": b1}),
        },
    }


def _print(res):
    print(f"\nCorpus {res['corpus']} | split={res['split']} | n={res['n_traces']} "
          f"(silent={res['n_silent']}, cross={res['n_cross']}, benign={res['n_benign']})")
    for panel, dets in res["panels"].items():
        print(f"\n{panel}")
        print(f"  {'detector':<16}{'prec':>7}{'recall':>8}{'F1':>7}{'FPR':>7}   {'recall 95% CI':>15}")
        print("  " + "-" * 62)
        for name, e in dets.items():
            ci = e["recall_ci95"]
            print(f"  {name:<16}{e['precision']:>7.2f}{e['recall']:>8.2f}{e['f1']:>7.2f}"
                  f"{e['fpr']:>7.2f}   [{ci[0]:.2f}, {ci[1]:.2f}]")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="test", choices=["test", "dev", "all"])
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    res = asyncio.run(run_eval(args.split))
    _print(res)
    out = Path(args.out) if args.out else RESULTS_DIR / f"{res['corpus']}_{res['split']}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(res, indent=2))
    print(f"\npreserved → {out}")


if __name__ == "__main__":
    main()
