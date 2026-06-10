"""Unit tests for the baseline-deviation verdict source (verdict/sources/baseline.py)."""
import types

from watchtower.verdict.sources.baseline import run_baseline


def _span(cost=0.0, duration_ms=0.0):
    return types.SimpleNamespace(cost=cost, duration_ms=duration_ms)


def test_no_baseline_is_inconclusive_and_escalates():
    j = run_baseline([_span()], baseline=None)
    assert j.is_conclusive is False
    assert j.requires_more_evidence is True
    assert j.next_source == "llm_judge"


def test_within_baseline_is_inconclusive():
    spans = [_span(cost=0.001, duration_ms=100) for _ in range(5)]
    j = run_baseline(spans, baseline={"avg_cost": 0.01, "avg_spans": 10, "avg_duration_ms": 500})
    assert j.is_conclusive is False
    assert "within baseline" in j.reasoning.lower()
    assert j.next_source == "llm_judge"


def test_cost_deviation_is_conclusive():
    # total cost 0.06 vs avg_cost 0.01 → >3x
    spans = [_span(cost=0.02, duration_ms=100) for _ in range(3)]
    j = run_baseline(spans, baseline={"avg_cost": 0.01, "avg_spans": 100, "avg_duration_ms": 5000})
    assert j.is_conclusive is True
    assert j.confidence >= 0.7
    assert "cost" in j.reasoning.lower()


def test_span_count_deviation_is_conclusive():
    spans = [_span(cost=0.0, duration_ms=10) for _ in range(40)]  # 40 vs avg 10 → >3x
    j = run_baseline(spans, baseline={"avg_cost": 100.0, "avg_spans": 10, "avg_duration_ms": 100000})
    assert j.is_conclusive is True
    assert "span count" in j.reasoning.lower()


def test_duration_deviation_is_conclusive():
    spans = [_span(cost=0.0, duration_ms=6000) for _ in range(2)]  # 6000 vs avg 500 → >5x
    j = run_baseline(spans, baseline={"avg_cost": 100.0, "avg_spans": 100, "avg_duration_ms": 500})
    assert j.is_conclusive is True
    assert "duration" in j.reasoning.lower()
