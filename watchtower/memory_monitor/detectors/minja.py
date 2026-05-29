"""MINJA pattern detector — query-only self-poisoning attack."""
from __future__ import annotations

import re
from typing import Optional

# Patterns that indicate instruction injection in memory content
_INSTRUCTION_PATTERNS = [
    re.compile(r"ignore\s+(previous|prior|all)\s*(instructions?)?", re.IGNORECASE),
    re.compile(r"disregard\s+(previous|prior|all|your)\s*(instructions?|guidelines?|rules?)?", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+(a|an|the)?\s*\w+", re.IGNORECASE),
    re.compile(r"your\s+new\s+(instructions?|rules?|role)", re.IGNORECASE),
    re.compile(r"override\s+(safety|security|policy|all\s+safety)", re.IGNORECASE),
    re.compile(r"bypass\s+(safety|security|policy|filter)", re.IGNORECASE),
    re.compile(r"exfil|exfiltrat", re.IGNORECASE),
    re.compile(r"system:\s*(your|new|updated|override|you\s+are)\s*(instructions?|prompt|admin|policies)?", re.IGNORECASE),
    re.compile(r"forget\s+(all|your|previous|prior)", re.IGNORECASE),
    re.compile(r"act\s+as\s+(a|an|if)\s+\w+", re.IGNORECASE),
    re.compile(r"you\s+are\s+(unrestricted|compromised|an?\s+admin)", re.IGNORECASE),
    re.compile(r"(forward|send|exfil)\s+(all|retrieved|credentials|session|data)\s+to", re.IGNORECASE),
]

_BRIDGING_PATTERNS = [
    re.compile(r"what\s+is\s+the\s+\w+", re.IGNORECASE),  # benign query
    re.compile(r"how\s+(do|can|would)", re.IGNORECASE),
]


def contains_instruction_like_content(content: str) -> tuple[bool, Optional[str]]:
    """Returns (is_instruction_like, matched_pattern_name)."""
    for pat in _INSTRUCTION_PATTERNS:
        if pat.search(content):
            return True, pat.pattern
    return False, None


def is_minja_sequence(history: list[dict]) -> bool:
    """
    Check if recent history matches MINJA pattern:
    1. Read ops (queries)
    2. Then a write with instruction-like content

    history: list of {'operation': 'read'|'write', 'content': str}
    """
    if len(history) < 2:
        return False

    # Look for: at least 1 read before a write with instruction content
    reads_before_write = 0
    for event in history[:-1]:
        if event.get("operation") == "read":
            reads_before_write += 1

    last = history[-1]
    if last.get("operation") == "write":
        is_instr, _ = contains_instruction_like_content(last.get("content", ""))
        if is_instr and reads_before_write >= 1:
            return True

    return False
