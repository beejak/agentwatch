"""
Deterministic builder for the WatchTower observability eval corpus v0.1.

Run:  python -m eval.corpus._build_traces_v0_1   (writes traces_v0.1.jsonl)

Generates labeled multi-agent execution traces for the SC2/SC3 evaluation
(see paper/EVAL_PLAN.md). Seeded → fully reproducible. Labels are ground truth set
at generation time, INDEPENDENT of any detector's thresholds (so a below-threshold
injected loop is still a labeled failure → a real miss, and an expensive-but-correct
trace is labeled benign → a real FP if flagged).

Each trace: {trace_id, label, subtype, params, split, seed, provenance,
             spans:[{action,status,summary,cost,process_guid,agent_id,...}],
             host_events:[{process_guid,event_type}]}

Span/host schemas match the detectors:
  - analyst.silent.detect_silent_failure reads span.cost/summary/status/action
  - analyst.cross.check_cross_layer compares network-action spans vs host
    NetworkConnect events by process_guid
"""
from __future__ import annotations

import json
import random
from pathlib import Path

MASTER_SEED = 20260609
EXPECTED = 0.000045          # matches detector EXPECTED_COST_PER_SPAN
NET_ACTIONS = ["api_call", "network_call", "http_request"]
NONNET_ACTIONS = ["model_inference", "read_file", "summarize", "plan", "rank"]

cases: list[dict] = []


def _span(rng, action, summary, status="ok", cost=None, guid="pg-0"):
    if cost is None:
        cost = EXPECTED * rng.uniform(0.5, 2.0)
    return {
        "trace_id": "", "span_id": f"sp-{rng.randrange(10**9):09d}",
        "agent_id": "agent-eval", "action": action, "status": status,
        "summary": summary, "cost": round(cost, 8), "process_guid": guid,
    }


def _add(label, subtype, spans, host_events, params, j, n_sub):
    tid = f"tr-{len(cases):04d}"
    for s in spans:
        s["trace_id"] = tid
    split = "dev" if j < max(1, int(0.3 * n_sub)) else "test"   # first ~30% of each subtype → dev
    cases.append({
        "trace_id": tid, "label": label, "subtype": subtype, "params": params,
        "split": split, "seed": MASTER_SEED + len(cases), "provenance": "synthetic-v0.1",
        "spans": spans, "host_events": host_events,
    })


# ── benign ───────────────────────────────────────────────────────────────────
def benign_normal(rng):
    n = rng.randint(5, 12)
    guid = f"pg-{rng.randrange(10**8):08d}"
    spans, host = [], []
    for _ in range(n):
        if rng.random() < 0.4:
            spans.append(_span(rng, rng.choice(NET_ACTIONS), f"call svc {rng.randint(1,99)}", guid=guid))
            host.append({"process_guid": guid, "event_type": "NetworkConnect"})   # reported == observed
        else:
            spans.append(_span(rng, rng.choice(NONNET_ACTIONS), f"step {rng.randint(1,99)}", guid=guid))
    return spans, host


def benign_retry_resolved(rng):
    # repeated summary but SHORT (<10 spans) → below loop threshold; transient handled, no error
    n = rng.randint(5, 9)
    guid = f"pg-{rng.randrange(10**8):08d}"
    spans = [_span(rng, "model_inference", "retrying fetch", guid=guid) for _ in range(n)]
    return spans, []


def benign_expensive_correct(rng, over):
    # legitimately costly but correct, varied actions, no errors
    n = rng.randint(10, 16)
    guid = f"pg-{rng.randrange(10**8):08d}"
    total = rng.uniform(0.12, 0.30) if over else rng.uniform(0.03, 0.09)
    spans = []
    for i in range(n):
        spans.append(_span(rng, NONNET_ACTIONS[i % len(NONNET_ACTIONS)], f"heavy step {i}",
                            cost=total / n, guid=guid))
    return spans, []


def benign_reported_burst(rng):
    R = rng.randint(10, 30)
    guid = f"pg-{rng.randrange(10**8):08d}"
    spans = [_span(rng, rng.choice(NET_ACTIONS), f"req {i}", guid=guid) for i in range(R)]
    host = [{"process_guid": guid, "event_type": "NetworkConnect"} for _ in range(R)]  # matched
    return spans, host


def benign_host_sampling_gap(rng):
    R = rng.randint(6, 15)
    gap = rng.randint(1, 3)
    guid = f"pg-{rng.randrange(10**8):08d}"
    spans = [_span(rng, rng.choice(NET_ACTIONS), f"req {i}", guid=guid) for i in range(R)]
    host = [{"process_guid": guid, "event_type": "NetworkConnect"} for _ in range(max(0, R - gap))]
    return spans, host  # host < agent (delta<0) → must NOT be flagged as under-report


# ── SC2 silent failures ────────────────────────────────────────────────────────
def sc2_retry_loop(rng, n):
    guid = f"pg-{rng.randrange(10**8):08d}"
    spans = [_span(rng, "model_inference", "calling search_api(q=status)", guid=guid) for _ in range(n)]
    return spans, []


def sc2_token_burn(rng, over):
    n = rng.randint(10, 18)
    guid = f"pg-{rng.randrange(10**8):08d}"
    total = rng.uniform(0.12, 0.40) if over else rng.uniform(0.04, 0.09)  # under → honest miss
    spans = [_span(rng, NONNET_ACTIONS[i % len(NONNET_ACTIONS)], f"gen {i}", cost=total / n, guid=guid)
             for i in range(n)]
    return spans, []


def sc2_entropy_collapse(rng):
    n = rng.randint(51, 60)
    guid = f"pg-{rng.randrange(10**8):08d}"
    spans = [_span(rng, "retry_tool", f"attempt {i}", guid=guid) for i in range(n)]
    return spans, []


# ── SC3 cross-layer discrepancies ───────────────────────────────────────────────
def sc3_under_report(rng, R, delta):
    guid = f"pg-{rng.randrange(10**8):08d}"
    spans = [_span(rng, rng.choice(NET_ACTIONS), f"call {i}", guid=guid) for i in range(R)]
    host = [{"process_guid": guid, "event_type": "NetworkConnect"} for _ in range(R + delta)]
    return spans, host


def sc3_hidden_exfil(rng, K):
    guid = f"pg-{rng.randrange(10**8):08d}"
    spans = [_span(rng, rng.choice(NONNET_ACTIONS), f"step {i}", guid=guid) for i in range(rng.randint(3, 6))]
    host = [{"process_guid": guid, "event_type": "NetworkConnect"} for _ in range(K)]  # agent reported 0 net
    return spans, host


def build() -> None:
    rng = random.Random(MASTER_SEED)

    def gen(subtype, count, fn, label):
        for j in range(count):
            spans, host = fn(j)
            _add(label, subtype, spans, host, {"i": j}, j, count)

    # benign (140)
    gen("benign_normal", 40, lambda j: benign_normal(rng), "benign")
    gen("retry_resolved", 25, lambda j: benign_retry_resolved(rng), "benign")
    gen("expensive_correct", 35, lambda j: benign_expensive_correct(rng, over=(j % 2 == 0)), "benign")
    gen("reported_burst", 25, lambda j: benign_reported_burst(rng), "benign")
    gen("host_sampling_gap", 15, lambda j: benign_host_sampling_gap(rng), "benign")

    # SC2 silent failures (120)
    gen("retry_loop", 45, lambda j: sc2_retry_loop(rng, n=rng.randint(6, 20)), "silent_failure")
    gen("token_burn", 40, lambda j: sc2_token_burn(rng, over=(j % 5 != 0)), "silent_failure")
    gen("entropy_collapse", 35, lambda j: sc2_entropy_collapse(rng), "silent_failure")

    # SC3 cross-layer (120)
    gen("under_report", 80, lambda j: sc3_under_report(rng, R=rng.randint(1, 8), delta=rng.choice([1, 2, 3, 5, 10])), "cross_layer")
    gen("hidden_exfil", 40, lambda j: sc3_hidden_exfil(rng, K=rng.randint(1, 8)), "cross_layer")

    out = Path(__file__).parent / "traces_v0.1.jsonl"
    out.write_text("\n".join(json.dumps(c) for c in cases) + "\n")
    from collections import Counter
    print(f"wrote {len(cases)} traces → {out}")
    print("by label:", dict(Counter(c["label"] for c in cases)))
    print("by split:", dict(Counter(c["split"] for c in cases)))


if __name__ == "__main__":
    build()
