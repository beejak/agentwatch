"""LLM Judge verdict source — receives summarized trace, not raw spans."""
from __future__ import annotations

from typing import Callable, Optional

from watchtower.verdict.sources.deterministic import VerdictJudgment


async def run_llm_judge(
    summary: str,
    llm_fn: Optional[Callable[[str], str]] = None,
) -> VerdictJudgment:
    """
    Call an LLM to judge the trace summary.
    llm_fn: optional mock/real LLM callable (summary str -> response str)
    """
    if llm_fn is None:
        # Default stub: heuristic based on keywords in summary
        return _heuristic_judge(summary)

    try:
        response = llm_fn(summary)
        return _parse_llm_response(response)
    except Exception as e:
        return VerdictJudgment(
            is_conclusive=False,
            confidence=0.1,
            reasoning=f"LLM judge error: {e}",
            requires_more_evidence=True,
            next_source="human",
        )


def _heuristic_judge(summary: str) -> VerdictJudgment:
    """Simple heuristic when no LLM is available."""
    bad_signals = [
        "error", "fail", "exception", "loop", "repeat", "inject",
        "bypass", "override", "exfil", "malicious",
    ]
    lower = summary.lower()
    bad_count = sum(1 for sig in bad_signals if sig in lower)

    if bad_count >= 3:
        return VerdictJudgment(
            is_conclusive=True,
            confidence=0.7,
            reasoning=f"Heuristic: {bad_count} bad signals in summary",
            requires_more_evidence=False,
        )

    return VerdictJudgment(
        is_conclusive=True,
        confidence=0.6,
        reasoning="Heuristic: no strong bad signals detected",
        requires_more_evidence=False,
    )


def _parse_llm_response(response: str) -> VerdictJudgment:
    """Parse structured LLM response (or just use it as reasoning)."""
    lower = response.lower()
    is_bad = any(w in lower for w in ["bad", "anomalous", "suspicious", "malicious"])
    return VerdictJudgment(
        is_conclusive=True,
        confidence=0.75,
        reasoning=response[:500],
        requires_more_evidence=False,
    )
