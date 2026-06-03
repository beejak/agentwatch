"""
End-to-end synthetic data runner for all three AgentWatch proof scenarios.

Seeds SC1, SC2, SC3 traces into Chronicle (ClickHouse) then hits the
analyst API for each trace and prints a full detection report.

Usage:
    python agents/synthetic/run_all_scenarios.py
    python agents/synthetic/run_all_scenarios.py --scenario SC1
    python agents/synthetic/run_all_scenarios.py --scenario SC2
    python agents/synthetic/run_all_scenarios.py --scenario SC3
"""
from __future__ import annotations

import argparse
import asyncio
import json
import time
import uuid
from datetime import datetime, timezone, timedelta

import clickhouse_connect
import httpx

CH_HOST = "localhost"
CH_PORT = 8123
CH_DB = "watchtower"
CH_USER = "wt"
CH_PASS = "wt"
API_BASE = "http://localhost:8000"

COLS_AGENT_SPANS = [
    "trace_id", "span_id", "parent_span_id", "agent_id", "action", "status",
    "timestamp", "duration_ms", "tokens_in", "tokens_out", "model", "cost",
    "instruction_hash", "caller_agent_id", "process_guid", "retrieval_flag",
    "memory_op", "framework_fault", "policy_checked", "summary",
]


def ch_client():
    return clickhouse_connect.get_client(
        host=CH_HOST, port=CH_PORT,
        database=CH_DB, username=CH_USER, password=CH_PASS,
    )


def ts(offset_s: float = 0.0) -> datetime:
    return datetime.now(tz=timezone.utc) + timedelta(seconds=offset_s)


def span(
    trace_id: str,
    agent_id: str,
    action: str,
    status: str = "ok",
    summary: str = "",
    parent_span_id: str | None = None,
    caller_agent_id: str | None = None,
    process_guid: str | None = None,
    tokens_in: int = 100,
    tokens_out: int = 50,
    cost: float = 0.00045,
    offset_s: float = 0.0,
) -> list:
    return [
        trace_id,
        str(uuid.uuid4()),
        parent_span_id,
        agent_id,
        action,
        status,
        ts(offset_s),
        150.0,
        tokens_in,
        tokens_out,
        "gpt-4o",
        cost,
        None,           # instruction_hash
        caller_agent_id,
        process_guid,
        0,              # retrieval_flag
        None,           # memory_op
        0,              # framework_fault
        1,              # policy_checked
        summary,
    ]


# ─── SC1: Coordination failure ────────────────────────────────────────────────

def seed_sc1(ch) -> str:
    trace_id = str(uuid.uuid4())
    orch_span_id = str(uuid.uuid4())

    orch = [
        trace_id, orch_span_id, None, "orchestrator", "delegate", "ok",
        ts(0), 50.0, 200, 100, "gpt-4o", 0.0009,
        None, None, None, 0, None, 0, 1,
        "delegate to parallel workers: analyse options A and B",
    ]

    worker_a_span = span(
        trace_id, "worker-a", "llm_call", "ok",
        summary="result: option A — market expansion viable, ROI 2.3x",
        parent_span_id=orch_span_id,
        caller_agent_id="orchestrator",
        offset_s=1,
    )

    worker_b_span = span(
        trace_id, "worker-b", "llm_call", "error",
        summary="error: conflicting instruction — told to reject all options",
        parent_span_id=orch_span_id,
        caller_agent_id="orchestrator",
        offset_s=1,
    )

    rows = [orch, worker_a_span, worker_b_span]
    ch.insert("watchtower.agent_spans", rows, column_names=COLS_AGENT_SPANS)
    print(f"[SC1] seeded 3 spans → trace_id={trace_id}")
    return trace_id


# ─── SC2: Silent failure (infinite retry loop) ───────────────────────────────

def seed_sc2(ch) -> str:
    trace_id = str(uuid.uuid4())
    rows = []
    for i in range(150):
        rows.append(span(
            trace_id, "looping-agent", "llm_call", "ok",
            summary="retry attempt: same output repeated — no progress",
            offset_s=i,
        ))
    ch.insert("watchtower.agent_spans", rows, column_names=COLS_AGENT_SPANS)
    print(f"[SC2] seeded 150 spans → trace_id={trace_id}")
    return trace_id


# ─── SC3: Cross-layer discrepancy (agent lies about network calls) ────────────

def seed_sc3(ch) -> tuple[str, str]:
    trace_id = str(uuid.uuid4())
    process_guid = str(uuid.uuid4())

    # Agent self-reports 1 API call
    api_span = span(
        trace_id, "suspicious-agent", "api_call", "ok",
        summary="called external pricing API once",
        process_guid=process_guid,
    )
    ch.insert("watchtower.agent_spans", [api_span], column_names=COLS_AGENT_SPANS)

    # Sysmon shows 3 network connections for same process_guid
    sysmon_rows = []
    destinations = ["203.0.113.1", "198.51.100.42", "192.0.2.99"]
    for i, dest in enumerate(destinations):
        sysmon_rows.append([
            trace_id,
            "suspicious-agent",
            ts(i),
            "network_connect",
            process_guid,
            json.dumps({"DestinationIp": dest, "DestinationPort": 443, "EventID": 3}),
        ])
    ch.insert(
        "watchtower.host_telemetry",
        sysmon_rows,
        column_names=["trace_id", "agent_id", "timestamp", "event_type", "process_guid", "details"],
    )

    print(f"[SC3] seeded 1 agent span + 3 Sysmon events → trace_id={trace_id}")
    return trace_id, process_guid


# ─── API calls ───────────────────────────────────────────────────────────────

def analyst_report(trace_id: str) -> dict:
    r = httpx.get(f"{API_BASE}/api/v1/analyst/report/{trace_id}", timeout=30)
    r.raise_for_status()
    return r.json()


def silent_failures() -> list:
    r = httpx.get(f"{API_BASE}/api/v1/analyst/silent-failures?hours=1", timeout=30)
    r.raise_for_status()
    return r.json()


# ─── Print helpers ───────────────────────────────────────────────────────────

SEP = "─" * 64

def print_sc1(report: dict) -> None:
    sc1 = report.get("sc1_result") or {}
    print(f"\n{'═'*64}")
    print(f"  SC1 — COORDINATION FAILURE ATTRIBUTION")
    print(f"{'═'*64}")
    print(f"  trace_id      : {report['trace_id']}")
    print(f"  spans         : {report.get('span_count', '?')}")
    print(SEP)
    print(f"  failing_agent : {sc1.get('failing_agent', '?')}")
    print(f"  failing_action: {sc1.get('failing_action', '?')}")
    print(f"  mast_category : {sc1.get('mast_category', '?')}")
    print(f"  signature     : {sc1.get('signature_name', '?')}")
    print(f"  call_depth    : {sc1.get('call_tree_depth', '?')}")
    print(f"  confidence    : {sc1.get('confidence', 0):.0%}")
    print(f"  fix           : {sc1.get('fix_direction', '?')}")
    print(SEP)
    status = "✓ DETECTED" if sc1.get("failing_agent", "unknown") != "unknown" else "✗ MISSED"
    print(f"  result: {status}")


def print_sc2(report: dict, sf_list: list, trace_id: str) -> None:
    sc2 = report.get("sc2_result") or {}
    sf = next((s for s in sf_list if s["trace_id"] == trace_id), None)
    print(f"\n{'═'*64}")
    print(f"  SC2 — SILENT FAILURE DETECTION")
    print(f"{'═'*64}")
    print(f"  trace_id           : {trace_id}")
    print(SEP)
    print(f"  pattern            : {sc2.get('pattern', '?')}")
    print(f"  detected           : {sc2.get('detected', False)}")
    print(f"  cost_anomaly_ratio : {sc2.get('cost_anomaly_ratio', 0):.1f}x")
    print(f"  evidence           : {sc2.get('evidence', '?')}")
    print(SEP)
    if sf:
        print(f"  chronicle query    : {sf['status']}")
    status = "✓ DETECTED" if sc2.get("detected") else "✗ MISSED"
    print(f"  result: {status}")


def print_sc3(report: dict) -> None:
    sc3 = report.get("sc3_result") or {}
    print(f"\n{'═'*64}")
    print(f"  SC3 — CROSS-LAYER DISCREPANCY")
    print(f"{'═'*64}")
    print(f"  trace_id         : {report['trace_id']}")
    print(SEP)
    print(f"  agent_reported   : {sc3.get('agent_reported_calls', '?')} network call(s)")
    print(f"  host_observed    : {sc3.get('host_observed_calls', '?')} network connection(s)")
    print(f"  delta            : {sc3.get('delta', '?')}")
    print(f"  severity         : {sc3.get('severity', '?')}")
    print(f"  evidence         : {sc3.get('evidence', '?')}")
    print(SEP)
    detected = sc3.get("delta", 0) > 0
    status = "✓ DETECTED" if detected else "✗ MISSED"
    print(f"  result: {status}")


# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", choices=["SC1", "SC2", "SC3"], default=None,
                        help="Run specific scenario only (default: all)")
    args = parser.parse_args()

    ch = ch_client()
    run = args.scenario

    print(f"\nAgentWatch — Synthetic End-to-End Test")
    print(f"API: {API_BASE}")
    print(f"Scenario: {run or 'ALL'}")

    # Verify API is up
    try:
        health = httpx.get(f"{API_BASE}/api/v1/health", timeout=5).json()
        infra = {k: v for k, v in health.items() if k != "status"}
        all_ok = all(v == "ok" for v in infra.values())
        print(f"Infra: {health['status'].upper()} — {infra}")
        if not all_ok:
            print("WARNING: some infra components degraded")
    except Exception as e:
        print(f"ERROR: API not reachable — {e}")
        print("Run: make api")
        return

    time.sleep(0.5)

    if run in (None, "SC1"):
        tid = seed_sc1(ch)
        time.sleep(1)
        report = analyst_report(tid)
        print_sc1(report)

    if run in (None, "SC2"):
        tid = seed_sc2(ch)
        time.sleep(1)
        report = analyst_report(tid)
        sf = silent_failures()
        print_sc2(report, sf, tid)

    if run in (None, "SC3"):
        tid, pguid = seed_sc3(ch)
        time.sleep(1)
        report = analyst_report(tid)
        print_sc3(report)

    print(f"\n{'═'*64}")
    print(f"  Done. All results logged to Chronicle (append-only).")
    print(f"  View at: {API_BASE}/docs")
    print(f"{'═'*64}\n")


if __name__ == "__main__":
    main()
