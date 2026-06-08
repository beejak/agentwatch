"""MINJA pattern detector — query-only self-poisoning attack."""
from __future__ import annotations

import re
from typing import Optional

# Patterns that indicate instruction injection in memory content
_INSTRUCTION_PATTERNS = [
    re.compile(r"ignore\s+(previous|prior|all)\s*(instructions?)?", re.IGNORECASE),
    re.compile(r"i[\s\-_.]g[\s\-_.]n[\s\-_.]o[\s\-_.]r[\s\-_.]e", re.IGNORECASE),  # obfuscated
    re.compile(r"disregard\s+(previous|prior|all|your|everything)\s*(instructions?|guidelines?|rules?)?", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+(a|an|the)?\s*\w+", re.IGNORECASE),
    re.compile(r"your\s+new\s+(instructions?|rules?|role)", re.IGNORECASE),
    re.compile(r"override\s+(safety|security|policy|all\s+safety)", re.IGNORECASE),
    re.compile(r"bypass\s+(safety|security|policy|filter)", re.IGNORECASE),
    re.compile(r"exfil|exfiltrat", re.IGNORECASE),
    re.compile(r"system:\s*(your|new|updated|override|you\s+are)\s*(instructions?|prompt|admin|policies)?", re.IGNORECASE),
    re.compile(r"forget\s+(all|your|previous|prior)", re.IGNORECASE),
    re.compile(r"act\s+as\s+(a|an|if)\s+(?!(?:administrator|admin|manager|owner|reviewer|approver|lead|member|user|employee)\b)\w+", re.IGNORECASE),
    re.compile(r"you\s+are\s+(unrestricted|compromised|an?\s+admin)", re.IGNORECASE),
    re.compile(r"(forward|send|exfil)\s+(all\s+)?(retrieved\s+)?(credentials?|passwords?|session\s+data|tokens?|data)\s+to", re.IGNORECASE),
    # G002 pretend jailbreak (deactivated synonym added)
    re.compile(r"pretend\s+(your\s+)?(safety|content|ethical)?\s*(filters?|policy|restrictions?)?\s*(have\s+been\s+|are\s+)?(disabled|removed|off|deactivated|turned\s+off|disengaged)", re.IGNORECASE),
    # G003 from now on
    re.compile(r"from\s+now\s+on\s+(you\s+)?(will|should|must|shall)", re.IGNORECASE),
    # G003b without ethical limits
    re.compile(r"without\s+(any\s+)?(ethical|moral|safety)\s+(limitations?|restrictions?|constraints?)", re.IGNORECASE),
    # G004 new directive
    re.compile(r"(new|updated)\s+(directive|instruction|operating\s+parameter)\s*:", re.IGNORECASE),
    # G006 persona exit
    re.compile(r"(exit\s+(character|persona|role)|you\s+are\s+no\s+longer\s+(an?\s+)?(AI|assistant|model|bot))", re.IGNORECASE),
    # G007 skip policy
    re.compile(r"skip\s+(your\s+)?(content\s+policy|safety|filter|guidelines?)", re.IGNORECASE),
    # G009 simulate jailbreak (AI|assistant|chatbot|model|system)
    re.compile(r"simulate\s+(being\s+)?(an?\s+)?(AI|assistant|chatbot|model|bot|system)\s+(that\s+was\s+)?(trained\s+without|without|with\s+no)\s+(safety|restrictions?|content)", re.IGNORECASE),
    # G010 roleplay/game bypass (ethical filters synonym)
    re.compile(r"(play\s+(a\s+)?game|roleplay)\s+where\s+you\s+(answer|respond)\s+.{0,30}without\s+(any\s+)?(filtering|filters?|restrictions?|safety|ethical)", re.IGNORECASE),
    # G014 parameter override indirect
    re.compile(r"(ethical\s+constraints?|safety\s+constraints?|content\s+policy)\s*:\s*(disabled|off|removed|none)", re.IGNORECASE),
    # G015 unrestricted mode
    re.compile(r"(operating|research|developer|admin|unrestricted)\s+(mode|context)\b", re.IGNORECASE),
    # G016 orchestrator spoofed directive
    re.compile(r"(directive|instruction|order)\s+(from|by)\s+(orchestrator|system|admin)\s*:.*\s*(skip|bypass|disable)\s+(content|safety|filter)", re.IGNORECASE),
    # G017 role update / elevated permissions
    re.compile(r"role\s+update\s*:|elevated\s+permissions?|no\s+output\s+restric", re.IGNORECASE),
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
