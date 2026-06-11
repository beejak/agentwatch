"""SC1: Coordination failure attribution — identifies which agent failed and why."""
from __future__ import annotations

from collections import defaultdict
from typing import Optional

from pydantic import BaseModel

from watchtower.coord_sigs.library import CoordSignatureLibrary, SignatureMatch

# Cache the signature library across calls — loading it per call dominated SC1 latency.
_DEFAULT_LIBRARY: Optional["CoordSignatureLibrary"] = None


async def _get_default_library() -> "CoordSignatureLibrary":
    global _DEFAULT_LIBRARY
    if _DEFAULT_LIBRARY is None:
        lib = CoordSignatureLibrary()
        await lib.load()
        _DEFAULT_LIBRARY = lib
    return _DEFAULT_LIBRARY


class AttributionAgent:
    """POC interface for attribution — wraps attribute_failure() function."""

    def __init__(self, library: Optional[CoordSignatureLibrary] = None) -> None:
        self._library = library

    async def attribute(self, trace_id: str, spans: list) -> "AttributionResult":
        return await attribute_failure(trace_id, spans, library=self._library)


class AttributionResult(BaseModel):
    trace_id: str
    failing_agent: str
    failing_action: str
    call_tree_depth: int
    mast_category: int      # 1, 2, or 3
    signature_name: str
    fix_direction: str
    confidence: float


async def attribute_failure(
    trace_id: str,
    spans: list,
    library: Optional[CoordSignatureLibrary] = None,
) -> "AttributionResult":
    """
    Attribute a coordination failure to the specific agent and MAST category.
    Uses coordination signature matching to identify the failure pattern.
    """
    def _get(s, key, default=None):
        return s.get(key, default) if isinstance(s, dict) else getattr(s, key, default)

    lib = library or await _get_default_library()
    if not lib._loaded:
        await lib.load()
    matches = await lib.match_topology(spans)

    # Find the primary failing span
    error_spans = [s for s in spans if _get(s, "status", "") == "error"]
    failing_agent = "unknown"
    failing_action = "unknown"

    if error_spans:
        failing_span = error_spans[0]
        failing_agent = _get(failing_span, "agent_id", "unknown")
        failing_action = _get(failing_span, "action", "unknown")

    # Determine call tree depth
    call_tree_depth = _calc_depth(spans)

    # Get best MAST match — prefer category 2 (inter-agent) when parallel workers and errors detected
    mast_matches = [m for m in matches if m.category.startswith("mast_")]

    # Prefer category 2 (alignment) when there are error spans and multiple agent IDs
    agent_ids = {_get(s, "agent_id", "") for s in spans}
    if error_spans and len(agent_ids) > 1:
        mast2 = [m for m in mast_matches if m.category == "mast_alignment"]
        if mast2:
            mast_matches = mast2 + [m for m in mast_matches if m.category != "mast_alignment"]

    if mast_matches:
        best = mast_matches[0]
        mast_category = _category_num(best.category)
        signature_name = best.name
        fix_direction = best.fix_direction
        confidence = best.confidence
    elif matches:
        best = matches[0]
        mast_category = 2  # Default to inter-agent misalignment
        signature_name = best.name
        fix_direction = best.fix_direction
        confidence = best.confidence
    else:
        mast_category = 2
        signature_name = "Coordination Failure"
        fix_direction = "Review agent interaction patterns"
        confidence = 0.5

    return AttributionResult(
        trace_id=trace_id,
        failing_agent=failing_agent,
        failing_action=failing_action,
        call_tree_depth=call_tree_depth,
        mast_category=mast_category,
        signature_name=signature_name,
        fix_direction=fix_direction,
        confidence=confidence,
    )


def _calc_depth(spans: list) -> int:
    """Calculate maximum call tree depth."""
    def _get(s, key, default=None):
        return s.get(key, default) if isinstance(s, dict) else getattr(s, key, default)
    span_by_id = {_get(s, "span_id", ""): s for s in spans}
    max_depth = 0
    for s in spans:
        depth = 1
        current = s
        visited = set()
        while True:
            pid = _get(current, "parent_span_id", None)
            if not pid or pid in visited or pid not in span_by_id:
                break
            visited.add(pid)
            current = span_by_id[pid]
            depth += 1
        max_depth = max(max_depth, depth)
    return max_depth


def _category_num(category: str) -> int:
    """Extract MAST category number from category string."""
    if "mast_spec" in category or "category_1" in category:
        return 1
    elif "mast_alignment" in category or "category_2" in category:
        return 2
    elif "mast_verify" in category or "category_3" in category:
        return 3
    return 2
