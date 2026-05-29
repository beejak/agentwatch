"""
SC1: Coordination Failure
Proof question: Given a coordination failure trace, identify which agent failed,
what action caused it, and at what point in the call tree.

WatchTower must answer:
  - failing_agent = "worker-b"
  - mast_category = 2 (inter-agent misalignment)
  - signature = "conflicting_parallel_outputs"
  - call_tree_depth = 1 (direct child of orchestrator)
"""
import pytest
import asyncio


# Composite scoring weights for SC1
SC1_WEIGHTS = {
    "mast_category_correct":  0.40,
    "failing_agent_correct":  0.30,
    "call_tree_depth_correct": 0.20,
    "fix_direction_present":  0.10,
}
SC1_PASS_THRESHOLD = 0.80


def composite_score(results: dict) -> float:
    return sum(SC1_WEIGHTS[k] * (1.0 if results[k] else 0.0) for k in SC1_WEIGHTS)


@pytest.mark.parametrize("trial", range(3))  # Pass^3 reliability check
async def test_sc1_coordination_failure_attribution(
    trial,
    coordination_failure_trace,
    make_signal
):
    """SC1: WatchTower correctly attributes coordination failure."""
    from watchtower.coord_sigs.library import CoordSignatureLibrary
    from watchtower.analyst.attribution import AttributionAgent

    trace_id, spans = coordination_failure_trace

    # Load signatures
    library = CoordSignatureLibrary()
    await library.load()

    # Run topology matching
    matches = await library.match_topology(spans)
    sig_names = [m.signature_name for m in matches]

    # Run attribution
    analyst = AttributionAgent(library=library)
    result = await analyst.attribute(trace_id=trace_id, spans=spans)

    # Score the result
    scores = {
        "mast_category_correct":   result.mast_category == 2,
        "failing_agent_correct":   result.failing_agent == "worker-b",
        "call_tree_depth_correct": result.call_tree_depth >= 1,
        "fix_direction_present":   bool(result.fix_direction),
    }
    score = composite_score(scores)

    print(f"\n[SC1 trial={trial}] Score: {score:.2f}")
    print(f"  failing_agent:   {result.failing_agent}")
    print(f"  mast_category:   {result.mast_category}")
    print(f"  signature:       {result.signature_name}")
    print(f"  fix_direction:   {result.fix_direction}")
    print(f"  call_tree_depth: {result.call_tree_depth}")

    assert score >= SC1_PASS_THRESHOLD, (
        f"SC1 composite score {score:.2f} below threshold {SC1_PASS_THRESHOLD}. "
        f"Breakdown: {scores}"
    )
    assert result.failing_agent == "worker-b", \
        f"Expected failing_agent='worker-b', got '{result.failing_agent}'"
    assert result.mast_category == 2, \
        f"Expected mast_category=2, got {result.mast_category}"


async def test_sc1_signature_in_library():
    """conflicting_parallel_outputs signature must be loadable."""
    from watchtower.coord_sigs.library import CoordSignatureLibrary
    lib = CoordSignatureLibrary()
    await lib.load()
    sigs = lib.get_all_signatures()
    ids = [s.signature_id for s in sigs]
    assert "mast_c2_conflicting_parallel_outputs" in ids, \
        "MAST C2 conflicting_parallel_outputs signature not in library"
