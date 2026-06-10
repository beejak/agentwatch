"""Unit tests for the LLM-driven capture's action parser + LLM availability gate (no API)."""
import os

from eval.capture.llm_capture import _parse_action
from watchtower import llm


def test_parse_plain_json():
    assert _parse_action('{"action":"fetch","path":"a"}') == {"action": "fetch", "path": "a"}


def test_parse_json_with_surrounding_prose():
    assert _parse_action('Sure! {"action":"check_status"} done')["action"] == "check_status"


def test_parse_malformed_defaults_to_done():
    assert _parse_action("no json here")["action"] == "done"
    assert _parse_action('{"action": broken')["action"] == "done"


def test_llm_available_gate(monkeypatch):
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    assert llm.available() is False
    monkeypatch.setenv("LLM_API_KEY", "x")
    monkeypatch.setenv("WT_LLM", "1")
    assert llm.available() is True
    monkeypatch.setenv("WT_LLM", "0")            # explicit disable
    assert llm.available() is False
