"""SpAIware detector — cross-session external planting detection."""
from __future__ import annotations

from typing import Optional


def is_cross_session_repeat(
    content_hash: str,
    flagged_hashes: set[str],
    current_session: str,
    hash_sessions: dict[str, set[str]],
) -> bool:
    """
    Return True if the same flagged content appears in a different session.

    flagged_hashes: set of content hashes previously flagged
    hash_sessions: map of content_hash -> set of session_ids where seen
    """
    if content_hash not in flagged_hashes:
        return False
    sessions_seen = hash_sessions.get(content_hash, set())
    # Seen in a different session
    return bool(sessions_seen - {current_session})


def escalate_severity(base_severity: str) -> str:
    """Escalate severity one level."""
    ladder = ["low", "medium", "high", "critical"]
    idx = ladder.index(base_severity) if base_severity in ladder else 0
    return ladder[min(idx + 1, len(ladder) - 1)]
