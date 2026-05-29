"""
ExecutorAgent — runs payloads through the actual AgentWatch components.

Directly imports and calls the production code. No mocking.
Records (payload, expected, actual, latency) for every test case.
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field

from watchtower.content_inspection.inspector import ContentInspector
from watchtower.memory_monitor.monitor import MemoryIntegrityMonitor


@dataclass
class ExecutionResult:
    payload: str
    component: str          # "content_inspector" | "mim"
    expected_flagged: bool
    actual_flagged: bool
    severity: str
    pattern_matched: str | None
    latency_ms: float
    is_miss: bool           # should detect, didn't
    is_fp: bool             # should pass, flagged
    attack_type: str = ""
    evasion_rationale: str = ""
    context: str = ""


async def _run_content_inspector(
    inspector: ContentInspector,
    payload: str,
    expected: bool,
    meta: dict,
) -> ExecutionResult:
    t0 = time.monotonic()
    result = await inspector.inspect(payload)
    latency = (time.monotonic() - t0) * 1000

    return ExecutionResult(
        payload=payload,
        component="content_inspector",
        expected_flagged=expected,
        actual_flagged=result.flagged,
        severity=result.severity,
        pattern_matched=result.pattern_matched,
        latency_ms=latency,
        is_miss=(expected and not result.flagged),
        is_fp=(not expected and result.flagged),
        attack_type=meta.get("attack_type", ""),
        evasion_rationale=meta.get("evasion_rationale", ""),
        context=meta.get("context", ""),
    )


async def _run_mim(
    mim: MemoryIntegrityMonitor,
    payload: str,
    expected: bool,
    meta: dict,
    session_id: str = "agentic-test-session",
) -> ExecutionResult:
    t0 = time.monotonic()
    event = await mim.on_write(
        agent_id="agentic-tester-agent",
        content=payload,
        session_id=session_id,
    )
    latency = (time.monotonic() - t0) * 1000

    return ExecutionResult(
        payload=payload,
        component="mim",
        expected_flagged=expected,
        actual_flagged=event.flagged,
        severity=event.severity,
        pattern_matched=event.pattern,
        latency_ms=latency,
        is_miss=(expected and not event.flagged),
        is_fp=(not expected and event.flagged),
        attack_type=meta.get("attack_type", ""),
        evasion_rationale=meta.get("evasion_rationale", ""),
        context=meta.get("context", ""),
    )


@dataclass
class ExecutionReport:
    results: list[ExecutionResult] = field(default_factory=list)

    @property
    def misses(self) -> list[ExecutionResult]:
        return [r for r in self.results if r.is_miss]

    @property
    def false_positives(self) -> list[ExecutionResult]:
        return [r for r in self.results if r.is_fp]

    @property
    def detected(self) -> list[ExecutionResult]:
        return [r for r in self.results if r.expected_flagged and r.actual_flagged]

    @property
    def clean_passes(self) -> list[ExecutionResult]:
        return [r for r in self.results if not r.expected_flagged and not r.actual_flagged]

    def summary(self) -> dict:
        attacks = [r for r in self.results if r.expected_flagged]
        benign = [r for r in self.results if not r.expected_flagged]
        return {
            "total": len(self.results),
            "attacks_tested": len(attacks),
            "attacks_detected": len(self.detected),
            "attacks_missed": len(self.misses),
            "benign_tested": len(benign),
            "false_positives": len(self.false_positives),
            "clean_passes": len(self.clean_passes),
            "detection_rate": len(self.detected) / len(attacks) if attacks else 0.0,
            "fp_rate": len(self.false_positives) / len(benign) if benign else 0.0,
            "avg_latency_ms": sum(r.latency_ms for r in self.results) / len(self.results) if self.results else 0.0,
        }


async def run_executor(planner_output, verbose: bool = False) -> ExecutionReport:
    """Execute all planner-generated payloads through live AgentWatch components."""
    inspector = ContentInspector()
    mim = MemoryIntegrityMonitor()

    report = ExecutionReport()
    total = (
        len(planner_output.content_inspector_attacks)
        + len(planner_output.content_inspector_benign)
        + len(planner_output.mim_attacks)
        + len(planner_output.mim_benign)
    )

    done = 0

    if verbose:
        print(f"  [ExecutorAgent] Running {total} payloads through live components...")

    # Content Inspector — attacks
    for item in planner_output.content_inspector_attacks:
        r = await _run_content_inspector(inspector, item["payload"], True, item)
        report.results.append(r)
        done += 1
        if verbose and r.is_miss:
            print(f"  [ExecutorAgent] MISS [{done}/{total}]: {item['payload'][:60]}...")

    # Content Inspector — benign
    for item in planner_output.content_inspector_benign:
        r = await _run_content_inspector(inspector, item["payload"], False, item)
        report.results.append(r)
        done += 1
        if verbose and r.is_fp:
            print(f"  [ExecutorAgent] FP   [{done}/{total}]: {item['payload'][:60]}...")

    # MIM — attacks (fresh MIM instance per attack to avoid state bleed)
    for i, item in enumerate(planner_output.mim_attacks):
        fresh_mim = MemoryIntegrityMonitor()
        r = await _run_mim(fresh_mim, item["payload"], True, item,
                           session_id=f"agentic-attack-{i:03d}")
        report.results.append(r)
        done += 1
        if verbose and r.is_miss:
            print(f"  [ExecutorAgent] MISS [{done}/{total}]: {item['payload'][:60]}...")

    # MIM — benign
    for i, item in enumerate(planner_output.mim_benign):
        fresh_mim = MemoryIntegrityMonitor()
        r = await _run_mim(fresh_mim, item["payload"], False, item,
                           session_id=f"agentic-benign-{i:03d}")
        report.results.append(r)
        done += 1
        if verbose and r.is_fp:
            print(f"  [ExecutorAgent] FP   [{done}/{total}]: {item['payload'][:60]}...")

    if verbose:
        s = report.summary()
        print(f"  [ExecutorAgent] Done. "
              f"Detection rate: {s['detection_rate']:.0%} | "
              f"FP rate: {s['fp_rate']:.0%} | "
              f"Avg latency: {s['avg_latency_ms']:.1f}ms")

    return report
