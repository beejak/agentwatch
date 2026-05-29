"""Baseline Engine — orchestrates per-agent behavioral profiling."""
from __future__ import annotations

import asyncio
import math
import time
from collections import Counter
from typing import Optional

from watchtower.baseline.profile import AgentProfile, RESTRICTED_THRESHOLD
from watchtower.baseline.drift import check_step_deviation, compute_drift_score


class BaselineEngine:
    """
    Builds and maintains per-agent behavioral profiles.
    Profiles are in-memory for the POC (would be stored in Chronicle/PG in production).
    """

    def __init__(self, chronicle_reader=None) -> None:
        self._profiles: dict[str, AgentProfile] = {}
        self._trace_spans: dict[str, list[list]] = {}  # agent_id -> list of span-lists
        self._lock = asyncio.Lock()
        self._reader = chronicle_reader

    async def build_profile(self, agent_id: str) -> AgentProfile:
        """Build or rebuild profile from historical traces."""
        async with self._lock:
            traces = self._trace_spans.get(agent_id, [])
            # Return existing profile if no new traces to process
            existing = self._profiles.get(agent_id)

        if not traces:
            # Return already-set profile (e.g., from set_test_baseline)
            if existing:
                return existing
            # Try to load from Chronicle if reader available
            if self._reader:
                pass  # Would load from Chronicle in production

            profile = AgentProfile(
                agent_id=agent_id,
                trace_count=0,
                restricted_mode=True,
            )
            async with self._lock:
                self._profiles[agent_id] = profile
            return profile

        return await self._compute_profile(agent_id, traces)

    async def _compute_profile(self, agent_id: str, traces: list[list]) -> AgentProfile:
        """Compute profile statistics from historical traces."""
        step_counts = [len(t) for t in traces]
        all_spans = [s for t in traces for s in t]

        n = len(traces)
        avg_step = sum(step_counts) / n
        std_step = math.sqrt(sum((x - avg_step) ** 2 for x in step_counts) / max(n - 1, 1))

        avg_cost = sum(getattr(s, "cost", 0.0) for s in all_spans) / max(len(all_spans), 1)
        avg_dur = sum(getattr(s, "duration_ms", 0.0) for s in all_spans) / max(len(all_spans), 1)
        avg_tok_in = sum(getattr(s, "tokens_in", 0) for s in all_spans) / max(len(all_spans), 1)
        avg_tok_out = sum(getattr(s, "tokens_out", 0) for s in all_spans) / max(len(all_spans), 1)

        action_counter = Counter(getattr(s, "action", "") for s in all_spans)
        common_actions = [a for a, _ in action_counter.most_common(5)]

        profile = AgentProfile(
            agent_id=agent_id,
            trace_count=n,
            restricted_mode=n < RESTRICTED_THRESHOLD,
            avg_step_count=avg_step,
            std_step_count=std_step,
            avg_duration_ms=avg_dur,
            avg_cost=avg_cost,
            avg_tokens_in=avg_tok_in,
            avg_tokens_out=avg_tok_out,
            common_actions=common_actions,
            avg_write_count=0.0,
            last_updated=time.time(),
        )

        async with self._lock:
            self._profiles[agent_id] = profile

        return profile

    async def check_deviation(self, agent_id: str, spans: list) -> Optional[str]:
        """Returns deviation description if anomalous, None if normal."""
        async with self._lock:
            profile = self._profiles.get(agent_id)

        if profile is None:
            profile = await self.build_profile(agent_id)

        if profile.trace_count == 0:
            return None  # No baseline to compare against

        # Check step count deviation
        step_dev = check_step_deviation(len(spans), profile)
        if step_dev:
            return step_dev

        # Check cost deviation
        total_cost = sum(getattr(s, "cost", 0.0) for s in spans)
        if profile.avg_cost > 0 and total_cost > profile.avg_cost * 10:
            return f"Cost ${total_cost:.4f} is {total_cost/profile.avg_cost:.1f}x baseline avg"

        # Check duration deviation
        if spans:
            avg_dur = sum(getattr(s, "duration_ms", 0.0) for s in spans) / len(spans)
            if profile.avg_duration_ms > 0 and avg_dur > profile.avg_duration_ms * 5:
                return f"Duration {avg_dur:.0f}ms is {avg_dur/profile.avg_duration_ms:.1f}x baseline avg"

        return None

    async def is_restricted(self, agent_id: str) -> bool:
        """Return True if agent has fewer than 50 traces (restricted mode)."""
        async with self._lock:
            profile = self._profiles.get(agent_id)
        if profile is None:
            profile = await self.build_profile(agent_id)
        return profile.restricted_mode

    async def update_profile(self, agent_id: str, new_spans: list) -> None:
        """Update profile with a new trace's spans."""
        async with self._lock:
            traces = self._trace_spans.setdefault(agent_id, [])
            traces.append(list(new_spans))

        await self._compute_profile(agent_id, self._trace_spans[agent_id])

    async def set_test_baseline(
        self,
        agent_id: str,
        avg_cost: float = 0.001,
        avg_step_count: float = 3.0,
        std_step_count: float = 1.0,
        avg_duration_ms: float = 200.0,
        trace_count: int = 100,
    ) -> None:
        """Directly set a test baseline profile (bypasses trace accumulation)."""
        profile = AgentProfile(
            agent_id=agent_id,
            trace_count=trace_count,
            restricted_mode=trace_count < RESTRICTED_THRESHOLD,
            avg_step_count=avg_step_count,
            std_step_count=std_step_count,
            avg_duration_ms=avg_duration_ms,
            avg_cost=avg_cost,
            avg_tokens_in=100.0,
            avg_tokens_out=50.0,
            common_actions=["llm_call"],
            avg_write_count=0.0,
            last_updated=time.time(),
        )
        async with self._lock:
            self._profiles[agent_id] = profile
