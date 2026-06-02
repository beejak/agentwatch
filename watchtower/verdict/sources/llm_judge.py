"""LLM Judge verdict source — receives summarized trace, not raw spans."""
from __future__ import annotations

import asyncio
import inspect
from typing import Callable, Optional

from watchtower.verdict.sources.deterministic import VerdictJudgment

_BAD_KEYWORDS = {"bad", "anomalous", "suspicious", "malicious"}
_HEURISTIC_BAD = [
    "error", "fail", "exception", "loop", "repeat", "inject",
    "bypass", "override", "exfil", "malicious",
]


async def run_llm_judge(
    summary: str,
    llm_fn: Optional[Callable[[str], str]] = None,
) -> VerdictJudgment:
    """Call an LLM (or heuristic stub) to judge a sanitised trace summary."""
    if llm_fn is None:
        return _heuristic_judge(summary)

    try:
        if inspect.iscoroutinefunction(llm_fn):
            response = await llm_fn(summary)
        else:
            response = await asyncio.get_event_loop().run_in_executor(None, llm_fn, summary)
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
    lower = summary.lower()
    bad_count = sum(1 for sig in _HEURISTIC_BAD if sig in lower)

    if bad_count >= 3:
        return VerdictJudgment(
            is_conclusive=True,
            confidence=0.7,
            reasoning=f"Heuristic: {bad_count} bad signals in summary",
            requires_more_evidence=False,
        )

    return VerdictJudgment(
        is_conclusive=True,
        confidence=0.3,
        reasoning="Heuristic: no strong bad signals detected",
        requires_more_evidence=False,
    )


def _parse_llm_response(response: str) -> VerdictJudgment:
    lower = response.lower()
    is_bad = any(w in lower for w in _BAD_KEYWORDS)
    confidence = 0.8 if is_bad else 0.2
    return VerdictJudgment(
        is_conclusive=True,
        confidence=confidence,
        reasoning=response[:500],
        requires_more_evidence=False,
    )
