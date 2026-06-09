"""
Observability eval sanity tests — deterministic, no external services.

Asserts corpus integrity and structural invariants (esp. H3: the self-report
baseline has zero recall on SC2/SC3). Does not assert exact WatchTower scores —
those are research results that move as the corpus grows.
"""
import json
from pathlib import Path

import pytest

from eval.harness import load_corpus, run_eval

CORPUS = Path("eval/corpus/traces_v0.1.jsonl")


def test_corpus_integrity():
    recs = [json.loads(l) for l in CORPUS.read_text().splitlines() if l.strip()]
    assert len(recs) >= 300
    assert len({r["trace_id"] for r in recs}) == len(recs)        # unique ids
    for r in recs:
        assert r["label"] in ("silent_failure", "cross_layer", "benign")
        assert r["split"] in ("dev", "test")
        assert r["spans"], "trace has no spans"
    test = [r for r in recs if r["split"] == "test"]
    assert len(test) >= 100
    for lbl in ("silent_failure", "cross_layer", "benign"):
        assert any(r["label"] == lbl for r in test), f"test split missing {lbl}"


async def test_harness_runs_and_reports():
    res = await run_eval("test")
    for panel in ("SC2_silent_failure", "SC3_cross_layer"):
        for det in res["panels"][panel].values():
            assert det["tp"] + det["fp"] + det["fn"] + det["tn"] == res["n_traces"]
            for m in ("precision", "recall", "f1", "fpr"):
                assert 0.0 <= det[m] <= 1.0


async def test_H3_self_report_blind_and_watchtower_better():
    """Core thesis: self-report baseline is blind (recall 0); WatchTower beats it."""
    res = await run_eval("test")
    sc2 = res["panels"]["SC2_silent_failure"]
    sc3 = res["panels"]["SC3_cross_layer"]
    # H3 — structural blindness of the self-report baseline
    assert sc2["self_report_B1"]["recall"] == 0.0
    assert sc3["self_report_B1"]["recall"] == 0.0
    # WatchTower strictly better than the blind baseline on both surfaces
    assert sc2["watchtower"]["recall"] > sc2["self_report_B1"]["recall"]
    assert sc3["watchtower"]["recall"] > sc3["self_report_B1"]["recall"]
