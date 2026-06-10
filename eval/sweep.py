"""
Operating-envelope sweeps — detection vs. magnitude across use cases.

Deterministic and fast. Maps the boundary where each detector starts/stops firing, so the
paper can show *where it works AND where it doesn't* (honest envelope, not just hits):

  - SC2 loop-length sweep  : silent-failure detection vs. retry-loop length
  - SC2 cost sweep         : token-burn detection vs. total cost
  - SC3 delta sweep        : cross-layer detection vs. host-minus-reported delta
                             (incl. negative delta = host-sampling gap → must NOT fire)
  - SC1 attribution        : single-error (root == first) vs. cascade (root != first error)

Run:  python -m eval.sweep    → eval/results/sweep_v0.1.json
"""
from __future__ import annotations

import asyncio
import json
import uuid
from pathlib import Path

from watchtower.analyst.silent import detect_silent_failure
from watchtower.analyst.cross import check_cross_layer
from watchtower.analyst.attribution import attribute_failure

RESULTS = Path(__file__).parent / "results" / "sweep_v0.1.json"


def _span(tid, action, summary, *, status="ok", cost=0.00005, guid="pg", parent=None, agent="a"):
    return {"trace_id": tid, "span_id": str(uuid.uuid4()), "parent_span_id": parent,
            "agent_id": agent, "action": action, "status": status, "summary": summary,
            "cost": cost, "process_guid": guid}


async def sc2_loop_curve():
    rows = []
    for k in range(4, 21):
        tid = f"loop-{k}"
        spans = [_span(tid, "model_inference", "retrying fetch(status=pending)") for _ in range(k)]
        r = await detect_silent_failure(tid, spans)
        rows.append({"loop_len": k, "detected": r.detected, "pattern": r.pattern})
    return rows


async def sc2_cost_curve():
    rows = []
    for cents in range(2, 31, 2):
        total = cents / 100.0
        tid = f"cost-{cents}"
        # 12 distinct actions/summaries (no loop/entropy) so only token-burn can fire
        spans = [_span(tid, f"act{i}", f"step {i}", cost=total / 12) for i in range(12)]
        r = await detect_silent_failure(tid, spans)
        rows.append({"total_cost": round(total, 2), "detected": r.detected, "pattern": r.pattern})
    return rows


async def sc3_delta_curve():
    rows = []
    reported = 5
    for delta in range(-3, 11):
        tid, guid = f"delta-{delta}", f"g{delta}"
        spans = [_span(tid, "http_request", "call", guid=guid) for _ in range(reported)]
        observed = max(0, reported + delta)
        host = [{"process_guid": guid, "event_type": "NetworkConnect"} for _ in range(observed)]
        r = await check_cross_layer(tid, spans, host)
        rows.append({"injected_delta": delta, "detector_delta": r.delta,
                     "detected": r.delta > 0, "severity": r.severity})
    return rows


async def sc1_attribution():
    """single-error (root == first error) vs cascade (root != first error)."""
    agents = ["worker-a", "worker-b", "worker-c"]
    cases = []

    # single error → naive 'first error span' attribution is correct
    tid = "attr-single"
    root = _span(tid, "delegate", "plan", agent="orchestrator")
    spans = [root] + [_span(tid, "tool_use", f"{a} work",
                            status=("error" if a == "worker-b" else "ok"),
                            parent=root["span_id"], agent=a) for a in agents]
    r = await attribute_failure(tid, spans)
    cases.append({"scenario": "single_error", "expected_root": "worker-b",
                  "attributed": r.failing_agent, "correct": r.failing_agent == "worker-b"})

    # cascade: worker-a fails first, which CAUSES worker-c to error later.
    # true root = worker-a; naive 'first error' also = worker-a → correct here,
    # but if the downstream error is ordered first, attribution misses the root.
    tid = "attr-cascade"
    root = _span(tid, "delegate", "plan", agent="orchestrator")
    # downstream (worker-c) error appears BEFORE the root (worker-a) error in span order
    spans = [root,
             _span(tid, "tool_use", "worker-c consumes bad input", status="error",
                   parent=root["span_id"], agent="worker-c"),
             _span(tid, "tool_use", "worker-a produced bad output", status="error",
                   parent=root["span_id"], agent="worker-a")]
    r = await attribute_failure(tid, spans)
    cases.append({"scenario": "cascade_root_not_first", "expected_root": "worker-a",
                  "attributed": r.failing_agent,
                  "correct": r.failing_agent == "worker-a",
                  "note": "limitation: attributes to first error span, not causal root"})
    acc = sum(1 for c in cases if c["correct"]) / len(cases)
    return {"accuracy": round(acc, 3), "cases": cases}


async def main():
    res = {
        "sc2_loop_curve": await sc2_loop_curve(),
        "sc2_cost_curve": await sc2_cost_curve(),
        "sc3_delta_curve": await sc3_delta_curve(),
        "sc1_attribution": await sc1_attribution(),
    }
    RESULTS.parent.mkdir(parents=True, exist_ok=True)
    RESULTS.write_text(json.dumps(res, indent=2))

    # readable envelope summary
    loop_on = min((r["loop_len"] for r in res["sc2_loop_curve"] if r["detected"]), default=None)
    cost_on = min((r["total_cost"] for r in res["sc2_cost_curve"] if r["detected"]), default=None)
    d_on = min((r["injected_delta"] for r in res["sc3_delta_curve"] if r["detected"]), default=None)
    print(f"SC2 silent-loop: fires at loop_len >= {loop_on} (misses shorter loops — honest)")
    print(f"SC2 token-burn : fires at total_cost >= ${cost_on} (FPs expensive-but-correct above this)")
    print(f"SC3 cross-layer: fires at injected_delta >= {d_on}; negative delta (host<agent) never fires")
    print(f"SC1 attribution: accuracy {res['sc1_attribution']['accuracy']} "
          f"(cascade case shows first-error != causal-root limitation)")
    print(f"\npreserved → {RESULTS}")


if __name__ == "__main__":
    asyncio.run(main())
