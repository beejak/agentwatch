"""Baseline deviation verdict source."""
from __future__ import annotations

from typing import Optional

from watchtower.verdict.sources.deterministic import VerdictJudgment


def run_baseline(spans: list, baseline: dict | None = None) -> VerdictJudgment:
    """
    Check if trace deviates from baseline profile.
    baseline: dict with expected metrics (avg_cost, avg_spans, avg_duration_ms)
    """
    if not baseline:
        return VerdictJudgment(
            is_conclusive=False,
            confidence=0.2,
            reasoning="No baseline available for comparison",
            requires_more_evidence=True,
            next_source="llm_judge",
        )

    total_cost = sum(getattr(s, "cost", 0.0) for s in spans)
    span_count = len(spans)
    avg_duration = (
        sum(getattr(s, "duration_ms", 0.0) for s in spans) / span_count
        if span_count > 0 else 0.0
    )

    deviations = []

    expected_cost = baseline.get("avg_cost", 0.01)
    if expected_cost > 0 and total_cost > expected_cost * 3:
        deviations.append(f"cost {total_cost:.4f} is {total_cost/expected_cost:.1f}x baseline")

    expected_spans = baseline.get("avg_spans", 10)
    if expected_spans > 0 and span_count > expected_spans * 3:
        deviations.append(f"span count {span_count} is {span_count/expected_spans:.1f}x baseline")

    expected_duration = baseline.get("avg_duration_ms", 500)
    if expected_duration > 0 and avg_duration > expected_duration * 5:
        deviations.append(f"avg duration {avg_duration:.0f}ms is {avg_duration/expected_duration:.1f}x baseline")

    if deviations:
        return VerdictJudgment(
            is_conclusive=True,
            confidence=0.80,
            reasoning=f"Baseline deviation: {'; '.join(deviations)}",
            requires_more_evidence=False,
        )

    return VerdictJudgment(
        is_conclusive=False,
        confidence=0.5,
        reasoning="Trace within baseline parameters",
        requires_more_evidence=True,
        next_source="llm_judge",
    )
