"""Coordination signature matcher — detects topology patterns in live traces."""
from __future__ import annotations

from collections import Counter
from typing import Optional


def _count_repeating_summaries(spans: list) -> tuple[str, int]:
    """Return (most_common_summary, count)."""
    summaries = [getattr(s, "summary", "") for s in spans if getattr(s, "summary", "")]
    if not summaries:
        return ("", 0)
    counter = Counter(summaries)
    most_common, count = counter.most_common(1)[0]
    return most_common, count


def _detect_parallel_workers(spans: list) -> dict[str, list]:
    """
    Detect spans with the same parent_span_id (parallel workers).
    Returns {parent_span_id: [child_spans]}.
    """
    parents: dict[str, list] = {}
    for s in spans:
        pid = getattr(s, "parent_span_id", None)
        if pid:
            parents.setdefault(pid, []).append(s)
    # Filter to groups with > 1 child
    return {pid: children for pid, children in parents.items() if len(children) > 1}


def _detect_sequential_chain_depth(spans: list) -> int:
    """Count the longest sequential chain (depth) via parent_span_id links."""
    span_by_id: dict[str, object] = {getattr(s, "span_id", ""): s for s in spans}
    max_depth = 0

    for s in spans:
        depth = 1
        current = s
        visited = set()
        while True:
            pid = getattr(current, "parent_span_id", None)
            if not pid or pid in visited or pid not in span_by_id:
                break
            visited.add(pid)
            current = span_by_id[pid]
            depth += 1
        max_depth = max(max_depth, depth)

    return max_depth


def match_signatures(spans: list, signatures: list[dict]) -> list[tuple[dict, float, list[str]]]:
    """
    Match spans against loaded signatures.
    Returns list of (signature, confidence, matched_agents).
    """
    results = []
    agent_ids = list({getattr(s, "agent_id", "unknown") for s in spans})

    # Pre-compute features
    total_cost = sum(getattr(s, "cost", 0.0) for s in spans)
    span_count = len(spans)
    error_spans = [s for s in spans if getattr(s, "status", "") == "error"]
    has_errors = len(error_spans) > 0
    _, max_repeat = _count_repeating_summaries(spans)
    parallel_groups = _detect_parallel_workers(spans)
    sequential_depth = _detect_sequential_chain_depth(spans)
    framework_faults = sum(1 for s in spans if getattr(s, "framework_fault", False))

    for sig in signatures:
        signals = sig.get("detection_signals", [])
        matched_signals = 0
        total_signals = len(signals)
        if total_signals == 0:
            continue

        for signal in signals:
            if signal == "span_count_exceeds_50" and span_count > 50:
                matched_signals += 1
            elif signal == "same_action_repeated_gt_5_times":
                actions = Counter(getattr(s, "action", "") for s in spans)
                if actions and actions.most_common(1)[0][1] > 5:
                    matched_signals += 1
            elif signal == "cost_anomaly_ratio_gt_10" and total_cost > 0.10:
                matched_signals += 1
            elif signal == "same_summary_repeated_gt_3" and max_repeat > 3:
                matched_signals += 1
            elif signal == "span_count_gt_50" and span_count > 50:
                matched_signals += 1
            elif signal == "no_error_status_in_trace" and not has_errors:
                matched_signals += 1
            elif signal == "multiple_agents_same_parent_span" and len(parallel_groups) > 0:
                matched_signals += 1
            elif signal == "one_or_more_worker_status_error" and has_errors:
                matched_signals += 1
            elif signal == "parallel_workers_gt_1" and len(parallel_groups) > 0:
                matched_signals += 1
            elif signal == "sequential_chain_depth_gt_3" and sequential_depth > 3:
                matched_signals += 1
            elif signal == "no_parent_span_references_downstream":
                # Check if there are spans with no parent (orphaned)
                no_parent = sum(1 for s in spans if not getattr(s, "parent_span_id", None))
                if no_parent == span_count:  # All are top-level → no feedback path
                    matched_signals += 1
            elif signal == "framework_fault_true" and framework_faults > 0:
                matched_signals += 1
            elif signal == "duplicate_tool_calls_across_agents":
                # Check if multiple agents called same action
                agent_actions: dict[str, set] = {}
                for s in spans:
                    aid = getattr(s, "agent_id", "")
                    act = getattr(s, "action", "")
                    agent_actions.setdefault(aid, set()).add(act)
                all_actions = [a for actions in agent_actions.values() for a in actions]
                if len(all_actions) != len(set(all_actions)):
                    matched_signals += 1
            elif signal == "identical_output_summaries" and max_repeat > 1:
                matched_signals += 1
            elif signal == "conflicting_outputs_same_domain":
                if len(set(agent_ids)) > 1 and has_errors:
                    matched_signals += 1

        if total_signals > 0:
            confidence = matched_signals / total_signals
            if confidence >= 0.4:  # At least 40% of signals matched
                results.append((sig, confidence, agent_ids))

    return results
