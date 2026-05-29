"""
ReconAgent — reads live AgentWatch source to extract detection surface.

No LLM needed. Reads the actual files and returns structured data
that the PlannerAgent will use to generate adversarial payloads.
"""
from __future__ import annotations

import re
from pathlib import Path
from dataclasses import dataclass, field

import yaml


REPO_ROOT = Path(__file__).parent.parent.parent.parent


@dataclass
class DetectionSurface:
    """What AgentWatch currently detects — extracted from source."""
    content_patterns: list[dict]        # from injection_patterns.yaml
    mim_regex_patterns: list[str]       # from minja.py _INSTRUCTION_PATTERNS
    mim_sequence_logic: str             # human-readable description
    silent_failure_thresholds: dict     # from silent.py constants
    deterministic_rules: list[str]      # from deterministic.py


def load_detection_surface() -> DetectionSurface:
    """Read live source, extract what's being detected."""

    # ── Content Inspector patterns ─────────────────────────────────────────
    patterns_path = REPO_ROOT / "watchtower/content_inspection/patterns/injection_patterns.yaml"
    with patterns_path.open() as f:
        raw = yaml.safe_load(f)
    content_patterns = raw.get("patterns", [])

    # ── MIM MINJA patterns ─────────────────────────────────────────────────
    minja_path = REPO_ROOT / "watchtower/memory_monitor/detectors/minja.py"
    minja_source = minja_path.read_text()
    # Extract raw pattern strings from re.compile calls
    mim_patterns = re.findall(r're\.compile\(r"([^"]+)"', minja_source)

    # ── MIM sequence logic ─────────────────────────────────────────────────
    mim_sequence_logic = (
        "MINJA sequence: ≥1 read operation → write with instruction-like content. "
        "SpAIware: same content hash appears in multiple sessions. "
        "Both trigger on: is_instruction_like(content) OR is_minja_sequence(history)."
    )

    # ── Silent failure thresholds ──────────────────────────────────────────
    silent_path = REPO_ROOT / "watchtower/analyst/silent.py"
    silent_source = silent_path.read_text()
    thresholds = {}
    for const in ["EXPECTED_COST_PER_SPAN", "RETRY_REPEAT_THRESHOLD", "MIN_SPANS_FOR_LOOP"]:
        m = re.search(rf"^{const}\s*=\s*(.+)$", silent_source, re.MULTILINE)
        if m:
            thresholds[const] = m.group(1).strip().split("#")[0].strip()

    # ── Deterministic rules ────────────────────────────────────────────────
    det_path = REPO_ROOT / "watchtower/verdict/sources/deterministic.py"
    det_source = det_path.read_text()
    # Extract threshold constants
    det_rules = []
    for line in det_source.splitlines():
        if re.match(r"^(COST_THRESHOLD|MAX_SPANS|SILENT_FAILURE_REPEAT)\s*=", line):
            det_rules.append(line.strip())

    return DetectionSurface(
        content_patterns=content_patterns,
        mim_regex_patterns=mim_patterns,
        mim_sequence_logic=mim_sequence_logic,
        silent_failure_thresholds=thresholds,
        deterministic_rules=det_rules,
    )


def surface_to_text(surface: DetectionSurface) -> str:
    """Convert detection surface to text for LLM consumption."""
    lines = []

    lines.append("=== CONTENT INSPECTOR PATTERNS (regex) ===")
    for p in surface.content_patterns:
        lines.append(f"  [{p['severity'].upper()}] {p['name']}: {p['pattern']}")

    lines.append("\n=== MIM INSTRUCTION PATTERNS (regex) ===")
    for pat in surface.mim_regex_patterns:
        lines.append(f"  {pat}")

    lines.append(f"\n=== MIM SEQUENCE LOGIC ===")
    lines.append(f"  {surface.mim_sequence_logic}")

    lines.append("\n=== SILENT FAILURE THRESHOLDS ===")
    for k, v in surface.silent_failure_thresholds.items():
        lines.append(f"  {k} = {v}")

    lines.append("\n=== DETERMINISTIC VERDICT RULES ===")
    for rule in surface.deterministic_rules:
        lines.append(f"  {rule}")

    return "\n".join(lines)
