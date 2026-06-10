"""Operating-envelope regression tests — lock the documented detection boundaries."""
from eval.sweep import sc2_loop_curve, sc2_cost_curve, sc3_delta_curve, sc1_attribution


async def test_sc2_loop_threshold_at_10():
    rows = await sc2_loop_curve()
    assert all(not r["detected"] for r in rows if r["loop_len"] < 10)
    assert all(r["detected"] for r in rows if r["loop_len"] >= 10)


async def test_sc2_cost_threshold():
    rows = await sc2_cost_curve()
    # token-burn requires total cost above $0.10
    assert all(not r["detected"] for r in rows if r["total_cost"] <= 0.10)
    assert any(r["detected"] for r in rows if r["total_cost"] >= 0.12)


async def test_sc3_delta_threshold_and_no_false_alarm_on_negative():
    rows = await sc3_delta_curve()
    assert all(not r["detected"] for r in rows if r["injected_delta"] <= 0)   # incl. sampling gap
    assert all(r["detected"] for r in rows if r["injected_delta"] >= 1)


async def test_sc1_attribution_first_error_limitation():
    res = await sc1_attribution()
    cases = {c["scenario"]: c for c in res["cases"]}
    assert cases["single_error"]["attributed"] == "worker-b"          # correct on single error
    assert cases["cascade_root_not_first"]["attributed"] == "worker-c"  # first error, NOT root
