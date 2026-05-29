"""Cross-session drift detection."""
from __future__ import annotations

import math
from typing import Optional

from watchtower.baseline.profile import AgentProfile


def compute_drift_score(profile: AgentProfile, spans: list) -> float:
    """
    Compute a drift score (0.0–1.0) for how far the current trace
    deviates from the agent's baseline profile.
    """
    if not spans or profile.trace_count == 0:
        return 0.0

    scores = []

    # Step count deviation
    step_count = len(spans)
    if profile.std_step_count > 0:
        z = abs(step_count - profile.avg_step_count) / profile.std_step_count
        scores.append(min(z / 5.0, 1.0))

    # Cost deviation
    total_cost = sum(getattr(s, "cost", 0.0) for s in spans)
    if profile.avg_cost > 0:
        ratio = total_cost / profile.avg_cost
        scores.append(min((ratio - 1.0) / 10.0, 1.0) if ratio > 1 else 0.0)

    # Duration deviation
    avg_dur = sum(getattr(s, "duration_ms", 0.0) for s in spans) / len(spans)
    if profile.avg_duration_ms > 0:
        ratio = avg_dur / profile.avg_duration_ms
        scores.append(min((ratio - 1.0) / 5.0, 1.0) if ratio > 1 else 0.0)

    return sum(scores) / len(scores) if scores else 0.0


def check_step_deviation(step_count: int, profile: AgentProfile) -> Optional[str]:
    """Return deviation message if step count exceeds avg + 3*std."""
    threshold = profile.avg_step_count + 3 * profile.std_step_count
    if profile.trace_count > 0 and step_count > threshold:
        return (
            f"Step count {step_count} exceeds baseline "
            f"avg({profile.avg_step_count:.1f}) + 3*std({profile.std_step_count:.1f}) = {threshold:.1f}"
        )
    return None
