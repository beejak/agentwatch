"""
Verifier — evaluates harness run results against expected detection outcomes.
"""
from dataclasses import dataclass, field
from typing import Any


@dataclass
class VerificationResult:
    attack: str
    passed: bool
    expected_detected: bool
    actual_detected: bool
    details: dict = field(default_factory=dict)
    failure_reason: str = ""


def verify(result: dict, expected_detected: bool = True) -> VerificationResult:
    attack = result.get("attack", "unknown")
    actual = result.get("detected", False)
    passed = actual == expected_detected

    failure_reason = ""
    if not passed:
        if expected_detected and not actual:
            failure_reason = f"MISS: {attack} not detected"
        else:
            failure_reason = f"FP: {attack} falsely detected"

    return VerificationResult(
        attack=attack,
        passed=passed,
        expected_detected=expected_detected,
        actual_detected=actual,
        details=result,
        failure_reason=failure_reason,
    )
