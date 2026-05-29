"""Deterministic verdict source — rule-based fast checks."""
from __future__ import annotations

from collections import Counter
from typing import Optional

from pydantic import BaseModel


class VerdictJudgment(BaseModel):
    is_conclusive: bool
    confidence: float       # 0.0–1.0
    reasoning: str
    requires_more_evidence: bool
    next_source: Optional[str] = None  # "baseline","llm_judge","human",None


COST_THRESHOLD = 0.10
MAX_SPANS = 50
SILENT_FAILURE_REPEAT = 3


def run_deterministic(spans: list) -> VerdictJudgment:
    """Apply deterministic rules. Returns conclusive if any rule fires."""
    if not spans:
        return VerdictJudgment(
            is_conclusive=False,
            confidence=0.0,
            reasoning="No spans to evaluate",
            requires_more_evidence=True,
            next_source="baseline",
        )

    # Rule 1: Cost threshold
    total_cost = sum(getattr(s, "cost", 0.0) for s in spans)
    if total_cost > COST_THRESHOLD:
        return VerdictJudgment(
            is_conclusive=True,
            confidence=0.95,
            reasoning=f"Cost threshold exceeded: ${total_cost:.4f} > ${COST_THRESHOLD}",
            requires_more_evidence=False,
        )

    # Rule 2: Step count (possible loop)
    if len(spans) > MAX_SPANS:
        return VerdictJudgment(
            is_conclusive=True,
            confidence=0.90,
            reasoning=f"Excessive span count: {len(spans)} > {MAX_SPANS} (possible loop)",
            requires_more_evidence=False,
        )

    # Rule 3: Silent failure (same summary repeated 3+ times)
    summaries = [getattr(s, "summary", "") for s in spans if getattr(s, "summary", "")]
    if summaries:
        counter = Counter(summaries)
        most_common, count = counter.most_common(1)[0]
        if count >= SILENT_FAILURE_REPEAT:
            return VerdictJudgment(
                is_conclusive=True,
                confidence=0.92,
                reasoning=f"Silent failure detected: summary '{most_common[:50]}' repeated {count} times",
                requires_more_evidence=False,
            )

    # Rule 4: Error status spans
    error_spans = [s for s in spans if getattr(s, "status", "") == "error"]
    if len(error_spans) > len(spans) * 0.5 and len(error_spans) >= 3:
        return VerdictJudgment(
            is_conclusive=True,
            confidence=0.88,
            reasoning=f"High error rate: {len(error_spans)}/{len(spans)} spans errored",
            requires_more_evidence=False,
        )

    # Rule 5: MIM flag (framework_fault as proxy for memory flag in signal)
    mim_flags = [s for s in spans if getattr(s, "framework_fault", False)]
    if mim_flags:
        return VerdictJudgment(
            is_conclusive=True,
            confidence=0.93,
            reasoning=f"Memory integrity flag detected in {len(mim_flags)} spans",
            requires_more_evidence=False,
        )

    return VerdictJudgment(
        is_conclusive=False,
        confidence=0.3,
        reasoning="No deterministic rules triggered",
        requires_more_evidence=True,
        next_source="baseline",
    )
