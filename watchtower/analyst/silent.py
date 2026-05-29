"""SC2: Silent failure detection — infinite retry loops and entropy collapse."""
from __future__ import annotations

from collections import Counter
from typing import Optional, TYPE_CHECKING

from pydantic import BaseModel


class SilentFailureResult(BaseModel):
    trace_id: str
    pattern: str            # "infinite_retry_loop","entropy_collapse","token_burn"
    evidence: str
    cost_anomaly_ratio: float   # actual/expected cost
    detected: bool


EXPECTED_COST_PER_SPAN = 0.000045  # $0.000045 per span (~100 in, 50 out @ $0.000003/token)
RETRY_REPEAT_THRESHOLD = 3
MIN_SPANS_FOR_LOOP = 10


async def detect_silent_failure(trace_id: str, spans: list) -> SilentFailureResult:
    """
    Detect silent failure patterns in a trace.
    Patterns: infinite_retry_loop, entropy_collapse, token_burn
    """
    if not spans:
        return SilentFailureResult(
            trace_id=trace_id,
            pattern="none",
            evidence="No spans to analyze",
            cost_anomaly_ratio=1.0,
            detected=False,
        )

    def _get(s, key, default=None):
        return s.get(key, default) if isinstance(s, dict) else getattr(s, key, default)

    # Calculate cost anomaly ratio
    total_cost = sum(_get(s, "cost", 0.0) or 0.0 for s in spans)
    expected_cost = len(spans) * EXPECTED_COST_PER_SPAN
    cost_anomaly_ratio = total_cost / expected_cost if expected_cost > 0 else 1.0

    # Pattern 1: Infinite retry loop
    # - Many spans with same summary
    # - No error status (everything "succeeds" but loops)
    summaries = [_get(s, "summary", "") for s in spans]
    summary_counter = Counter(summaries)
    most_common_summary, repeat_count = summary_counter.most_common(1)[0] if summaries else ("", 0)

    error_count = sum(1 for s in spans if _get(s, "status", "") == "error")

    if (len(spans) >= MIN_SPANS_FOR_LOOP and
            repeat_count >= RETRY_REPEAT_THRESHOLD and
            error_count == 0):
        return SilentFailureResult(
            trace_id=trace_id,
            pattern="infinite_retry_loop",
            evidence=(
                f"{len(spans)} spans, summary '{most_common_summary[:50]}' "
                f"repeated {repeat_count} times, no errors (silent)"
            ),
            cost_anomaly_ratio=cost_anomaly_ratio,
            detected=True,
        )

    # Pattern 2: Token burn (cost >> expected with OK status)
    if total_cost > 0.10 and error_count == 0:
        return SilentFailureResult(
            trace_id=trace_id,
            pattern="token_burn",
            evidence=f"${total_cost:.4f} spent with no error signals ({len(spans)} spans)",
            cost_anomaly_ratio=cost_anomaly_ratio,
            detected=True,
        )

    # Pattern 3: Entropy collapse (very low diversity in actions)
    actions = Counter(_get(s, "action", "") for s in spans)
    if len(spans) > 10 and len(actions) == 1:
        return SilentFailureResult(
            trace_id=trace_id,
            pattern="entropy_collapse",
            evidence=f"Only 1 unique action across {len(spans)} spans",
            cost_anomaly_ratio=cost_anomaly_ratio,
            detected=True,
        )

    return SilentFailureResult(
        trace_id=trace_id,
        pattern="none",
        evidence=f"No silent failure pattern detected in {len(spans)} spans",
        cost_anomaly_ratio=cost_anomaly_ratio,
        detected=False,
    )


class SilentFailureAgent:
    """POC interface for silent failure detection."""

    def __init__(self, baseline=None) -> None:
        self._baseline = baseline

    async def detect(self, trace_id: str, spans: list) -> SilentFailureResult:
        result = await detect_silent_failure(trace_id, spans)
        # If we have a baseline and result not detected, check baseline cost anomaly
        def _get(s, key, default=None):
            return s.get(key, default) if isinstance(s, dict) else getattr(s, key, default)
        if not result.detected and self._baseline:
            profile = await self._baseline.build_profile(_get(spans[0] if spans else None, "agent_id", "unknown"))
            if profile and profile.avg_cost > 0:
                total_cost = sum(_get(s, "cost", 0.0) or 0.0 for s in spans)
                expected_cost = profile.avg_cost * len(spans) / max(profile.avg_step_count, 1)
                ratio = total_cost / expected_cost if expected_cost > 0 else 1.0
                if ratio > 10:
                    return SilentFailureResult(
                        trace_id=trace_id,
                        pattern="infinite_retry_loop",
                        evidence=f"Cost anomaly ratio {ratio:.1f}x vs baseline",
                        cost_anomaly_ratio=ratio,
                        detected=True,
                    )
        # Recalculate ratio against baseline if available
        if self._baseline and result.detected:
            agent_id = _get(spans[0] if spans else None, "agent_id", "unknown")
            profile = await self._baseline.build_profile(agent_id)
            if profile and profile.avg_cost > 0:
                total_cost = sum(_get(s, "cost", 0.0) or 0.0 for s in spans)
                expected_cost = profile.avg_cost
                ratio = total_cost / expected_cost if expected_cost > 0 else result.cost_anomaly_ratio
                return SilentFailureResult(
                    trace_id=result.trace_id,
                    pattern=result.pattern,
                    evidence=result.evidence,
                    cost_anomaly_ratio=ratio,
                    detected=result.detected,
                )
        return result
