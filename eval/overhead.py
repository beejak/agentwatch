"""
Overhead / practicality benchmark — cost of observation.

Measures, over the frozen corpus, the per-trace detection latency for SC1/SC2/SC3, the
tier-0 content-inspection latency, and throughput (spans analyzed per second). Pure CPU,
no external services. Output: eval/results/overhead.json (consumed by the paper).

Run:  python -m eval.overhead
"""
from __future__ import annotations

import asyncio
import json
import statistics
import time
from pathlib import Path

from eval.harness import load_corpus
from watchtower.analyst.silent import detect_silent_failure
from watchtower.analyst.cross import check_cross_layer
from watchtower.analyst.attribution import attribute_failure
from watchtower.content_inspection.inspector import ContentInspector

RESULTS = Path(__file__).parent / "results" / "overhead.json"


async def _time(fn, iters: int) -> list[float]:
    samples = []
    for _ in range(iters):
        t0 = time.perf_counter()
        await fn()
        samples.append((time.perf_counter() - t0) * 1000.0)  # ms
    return samples


def _stats(samples: list[float]) -> dict:
    s = sorted(samples)
    return {
        "mean_ms": round(statistics.mean(s), 4),
        "p50_ms": round(s[len(s) // 2], 4),
        "p99_ms": round(s[min(len(s) - 1, int(0.99 * len(s)))], 4),
    }


async def main():
    traces = load_corpus("all")
    total_spans = sum(len(t["spans"]) for t in traces)
    inspector = ContentInspector()

    # Per-trace detector latency (averaged over the corpus, repeated).
    async def run_sc1():
        for t in traces:
            await attribute_failure(t["trace_id"], t["spans"])

    async def run_sc2():
        for t in traces:
            await detect_silent_failure(t["trace_id"], t["spans"])

    async def run_sc3():
        for t in traces:
            await check_cross_layer(t["trace_id"], t["spans"], t.get("host_events"))

    async def run_tier0():
        for t in traces:
            for s in t["spans"]:
                await inspector.inspect(s.get("summary", ""))

    iters = 5
    sc1 = await _time(run_sc1, iters)
    sc2 = await _time(run_sc2, iters)
    sc3 = await _time(run_sc3, iters)
    tier0 = await _time(run_tier0, iters)

    def per_trace(sweep_ms):  # total-corpus ms → per-trace ms
        return [m / len(traces) for m in sweep_ms]

    # Throughput: spans analyzed per second by the full SC1+SC2+SC3 pass.
    full_ms = statistics.mean(s1 + s2 + s3 for s1, s2, s3 in zip(sc1, sc2, sc3))
    spans_per_sec = round(total_spans / (full_ms / 1000.0))

    res = {
        "n_traces": len(traces), "total_spans": total_spans, "iters": iters,
        "per_trace_ms": {
            "SC1_attribution": _stats(per_trace(sc1)),
            "SC2_silent": _stats(per_trace(sc2)),
            "SC3_cross_layer": _stats(per_trace(sc3)),
        },
        "tier0_content_inspect_per_span": _stats([m / total_spans for m in tier0]),
        "throughput_spans_per_sec_full_analysis": spans_per_sec,
    }
    RESULTS.parent.mkdir(parents=True, exist_ok=True)
    RESULTS.write_text(json.dumps(res, indent=2))
    print(json.dumps(res, indent=2))
    print(f"\npreserved → {RESULTS}")


if __name__ == "__main__":
    asyncio.run(main())
