"""Trace Summariser — compresses traces for LLM Judge input."""
from __future__ import annotations

import random


MAX_SUMMARY_CHARS = 2000
SAMPLE_RATE = 0.1  # Keep 10% of middle spans


def summarise_trace(spans: list) -> str:
    """
    Compress a potentially large trace to under 2000 chars.
    Strategy: keep first span, last span, all error spans, all handoff spans, sample rest.
    """
    if not spans:
        return "(empty trace)"

    if len(spans) == 1:
        return _format_span(spans[0])

    keep = []

    # Always keep first and last
    keep.append(("first", spans[0]))
    keep.append(("last", spans[-1]))

    # Keep all error spans
    for s in spans[1:-1]:
        status = getattr(s, "status", "")
        action = getattr(s, "action", "")
        if status == "error":
            keep.append(("error", s))
        elif action in ("handoff", "delegate"):
            keep.append(("handoff", s))

    # Sample remaining spans
    middle = spans[1:-1]
    sample_count = max(1, int(len(middle) * SAMPLE_RATE))
    if middle:
        sampled = random.sample(middle, min(sample_count, len(middle)))
        for s in sampled:
            # Don't double-add already-kept spans
            if not any(kept_s is s for _, kept_s in keep):
                keep.append(("sampled", s))

    # Build summary
    lines = [f"Trace with {len(spans)} spans total:"]
    seen_ids = set()
    for label, span in keep:
        span_id = id(span)
        if span_id in seen_ids:
            continue
        seen_ids.add(span_id)
        lines.append(f"[{label}] {_format_span(span)}")

    summary = "\n".join(lines)

    # Truncate if still too long (ensure strictly < MAX_SUMMARY_CHARS)
    if len(summary) >= MAX_SUMMARY_CHARS:
        summary = summary[:MAX_SUMMARY_CHARS - 4] + "..."

    return summary


def _format_span(span) -> str:
    agent_id = getattr(span, "agent_id", "?")
    action = getattr(span, "action", "?")
    status = getattr(span, "status", "?")
    summary = getattr(span, "summary", "")[:80]
    cost = getattr(span, "cost", 0.0)
    return f"{agent_id} {action} [{status}] cost=${cost:.4f} summary='{summary}'"
