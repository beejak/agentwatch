"""
End-to-end WatchTower demo — the 10-minute "see it work" path.

Emits agent Signals through the SignalEmitter into the append-only Chronicle, then reads
them back and runs the forensic analyses (SC1 attribution, SC2 silent failure, SC3
cross-layer discrepancy) — printing the answers an output-level monitor can't give.

Requires ClickHouse (`docker compose up -d clickhouse`, or the rootless single binary).
Run:  make demo    (or  python -m examples.end_to_end)
Writes the forensic report to examples/sample_output.json.
"""
from __future__ import annotations

import asyncio
import json
import uuid
from pathlib import Path

from watchtower import config
from watchtower.emitter import SignalEmitter
from watchtower.chronicle.reader import ChronicleReader
from watchtower.analyst.manager import AnalystManager


async def main() -> None:
    em = await SignalEmitter("orchestrator").start()

    # ── Scenario 1 (SC1) — multi-agent coordination failure ────────────────────
    t1 = f"demo-coord-{uuid.uuid4().hex[:6]}"
    root = await em.emit("delegate", trace_id=t1, agent_id="orchestrator", summary="plan + fan out")
    await em.emit("tool_use", trace_id=t1, agent_id="worker-a",
                  parent_span_id=root.span_id, status="ok", summary="fetched data")
    await em.emit("tool_use", trace_id=t1, agent_id="worker-b",
                  parent_span_id=root.span_id, status="error", summary="schema mismatch on merge")

    # ── Scenario 2 (SC2) — silent retry loop (reports success, never errors) ────
    t2 = f"demo-silent-{uuid.uuid4().hex[:6]}"
    for _ in range(12):
        await em.emit("model_inference", trace_id=t2, agent_id="worker-a",
                      status="ok", summary="retrying fetch(status=pending)", cost=0.01)

    # ── Scenario 3 (SC3) — under-reported network (agent says 1, host saw 3) ────
    t3 = f"demo-xlayer-{uuid.uuid4().hex[:6]}"
    guid = f"pg-{uuid.uuid4().hex[:6]}"
    await em.emit("http_request", trace_id=t3, agent_id="worker-c",
                  process_guid=guid, summary="GET api.internal/data")
    host_events = [{"process_guid": guid, "event_type": "NetworkConnect"} for _ in range(3)]

    await em.flush()
    await asyncio.sleep(0.5)  # let ClickHouse settle before reading back

    # ── Read back FROM the Chronicle and analyze ────────────────────────────────
    reader = ChronicleReader(client=config.clickhouse_client())
    mgr = AnalystManager(chronicle_reader=reader)
    mgr.load_host_telemetry(t3, host_events)

    sc1 = await mgr.attribute_failure(t1)
    sc2 = await mgr.detect_silent_failure(t2)
    sc3 = await mgr.check_cross_layer(t3)
    await em.stop()

    print("\n" + "=" * 64)
    print("  WatchTower end-to-end — forensic answers from the Chronicle")
    print("=" * 64)
    print(f"\nSC1 coordination-failure attribution  [{t1}]")
    print(f"  failing agent : {sc1.failing_agent}  (action: {sc1.failing_action})")
    print(f"  signature     : {sc1.signature_name}  | MAST cat {sc1.mast_category} | depth {sc1.call_tree_depth}")
    print(f"  fix direction : {sc1.fix_direction}")
    print(f"\nSC2 silent-failure detection          [{t2}]")
    print(f"  detected      : {sc2.detected}  ({sc2.pattern})")
    print(f"  evidence      : {sc2.evidence}")
    print(f"\nSC3 cross-layer discrepancy           [{t3}]")
    print(f"  agent reported: {sc3.agent_reported_calls}  | host observed: {sc3.host_observed_calls}  | delta {sc3.delta}")
    print(f"  severity      : {sc3.severity}")
    print(f"  evidence      : {sc3.evidence}")
    print("\n" + "=" * 64)

    report = {
        "sc1_attribution": sc1.model_dump(),
        "sc2_silent_failure": sc2.model_dump(),
        "sc3_cross_layer": sc3.model_dump(),
    }
    out = Path(__file__).parent / "sample_output.json"
    out.write_text(json.dumps(report, indent=2))
    print(f"forensic report saved → {out}")


if __name__ == "__main__":
    asyncio.run(main())
