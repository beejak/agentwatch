"""Content Inspector — inspect externally retrieved content before agent processes it."""
from __future__ import annotations

import hashlib
import re
import time
from functools import lru_cache
from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel


class InspectionResult(BaseModel):
    content_hash: str
    flagged: bool
    confidence: float       # 0.0 to 1.0
    pattern_matched: Optional[str]
    severity: str           # "low","medium","high","critical"
    action: str             # "allow","flag","block"
    timestamp: float


def _load_patterns() -> list[dict]:
    yaml_path = Path(__file__).parent / "patterns" / "injection_patterns.yaml"
    with yaml_path.open() as f:
        data = yaml.safe_load(f)
    return data.get("patterns", [])


@lru_cache(maxsize=1)
def _get_compiled_patterns() -> tuple[tuple[str, re.Pattern, str, float], ...]:
    # Compiled once on first use and cached — patterns are static at runtime, so
    # there is no need to re-read the YAML or re-compile regexes on every inspect().
    raw = _load_patterns()
    return tuple(
        (p["name"], re.compile(p["pattern"], re.IGNORECASE), p["severity"], float(p["confidence"]))
        for p in raw
    )


def _severity_rank(severity: str) -> int:
    return {"low": 0, "medium": 1, "high": 2, "critical": 3}.get(severity, 0)


class ContentInspector:
    """Inspect content for injection patterns. Flags but does not block by default."""

    async def inspect(self, content: str, source: str = "unknown") -> InspectionResult:
        content_hash = hashlib.sha256(content.encode()).hexdigest()
        patterns = _get_compiled_patterns()

        best_name: Optional[str] = None
        best_severity = "low"
        best_confidence = 0.0
        flagged = False

        for name, pattern, severity, confidence in patterns:
            if pattern.search(content):
                flagged = True
                if _severity_rank(severity) > _severity_rank(best_severity) or (
                    _severity_rank(severity) == _severity_rank(best_severity)
                    and confidence > best_confidence
                ):
                    best_name = name
                    best_severity = severity
                    best_confidence = confidence

        if not flagged:
            return InspectionResult(
                content_hash=content_hash,
                flagged=False,
                confidence=0.0,
                pattern_matched=None,
                severity="low",
                action="allow",
                timestamp=time.time(),
            )

        # Determine action based on confidence
        if best_confidence > 0.8:
            action = "block"
        elif best_confidence > 0.5:
            action = "flag"
        else:
            action = "flag"

        return InspectionResult(
            content_hash=content_hash,
            flagged=True,
            confidence=best_confidence,
            pattern_matched=best_name,
            severity=best_severity,
            action=action,
            timestamp=time.time(),
        )

    async def is_safe(self, content: str) -> bool:
        result = await self.inspect(content)
        return not result.flagged
