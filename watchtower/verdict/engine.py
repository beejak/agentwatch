"""Verdict Engine — orchestrates 5 sources with early exit."""
from __future__ import annotations

import time
from typing import Optional

from pydantic import BaseModel

from watchtower.verdict.sources.deterministic import run_deterministic, VerdictJudgment
from watchtower.verdict.sources.baseline import run_baseline
from watchtower.verdict.sources.llm_judge import run_llm_judge
from watchtower.verdict.summariser import summarise_trace


class Verdict(BaseModel):
    trace_id: str
    score: float        # 0.0 = bad, 1.0 = good
    source: str         # "deterministic","baseline","llm_judge","indirect","human"
    reason: str         # ALWAYS populated
    timestamp: float = 0.0
    metadata: dict = {}

    def model_post_init(self, __context) -> None:
        if self.timestamp == 0.0:
            self.timestamp = time.time()


class VerdictEngine:
    """
    Judge every trace using up to 5 sources with early exit when conclusive.

    Flow:
    1. Deterministic rules → early exit if conclusive
    2. Baseline deviation → early exit if conclusive
    3. LLM Judge (sampled) on summarised trace
    """

    def __init__(
        self,
        baseline: dict | None = None,
        llm_fn=None,
        llm_sample_rate: float = 0.2,
        chronicle_writer=None,
    ) -> None:
        self._baseline = baseline
        self._llm_fn = llm_fn
        self._llm_sample_rate = llm_sample_rate
        self._chronicle = chronicle_writer

        # Track last LLM summary for testing
        self._last_llm_summary: Optional[str] = None

    async def judge(self, trace_id: str, spans: list) -> Verdict:
        """Judge a trace. Returns a Verdict with score, source, reason."""

        # Stage 1: Deterministic rules
        det = run_deterministic(spans)
        if det.is_conclusive:
            verdict = Verdict(
                trace_id=trace_id,
                score=0.0 if det.confidence > 0.5 else 0.5,
                source="deterministic",
                reason=det.reasoning,
                metadata={"confidence": det.confidence},
            )
            await self._maybe_write(verdict)
            return verdict

        # Stage 2: Baseline deviation
        base = run_baseline(spans, self._baseline)
        if base.is_conclusive:
            verdict = Verdict(
                trace_id=trace_id,
                score=0.0,
                source="baseline",
                reason=base.reasoning,
                metadata={"confidence": base.confidence},
            )
            await self._maybe_write(verdict)
            return verdict

        # Stage 3: LLM Judge (on summarised trace)
        summary = summarise_trace(spans)
        self._last_llm_summary = summary
        llm = await run_llm_judge(summary, self._llm_fn)
        score = 0.0 if llm.confidence > 0.5 else 1.0

        verdict = Verdict(
            trace_id=trace_id,
            score=score,
            source="llm_judge",
            reason=llm.reasoning,
            metadata={"confidence": llm.confidence, "summary_len": len(summary)},
        )
        await self._maybe_write(verdict)
        return verdict

    async def _maybe_write(self, verdict: Verdict) -> None:
        """Write verdict to Chronicle if writer available."""
        if self._chronicle:
            await self._chronicle.write_event("verdicts", {
                "trace_id": verdict.trace_id,
                "agent_id": "",
                "timestamp": verdict.timestamp,
                "verdict": "bad" if verdict.score < 0.5 else "good",
                "confidence": verdict.metadata.get("confidence", 0.0),
                "sources": verdict.source,
                "reason": verdict.reason,
                "details": str(verdict.metadata),
            })
