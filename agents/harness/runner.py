"""
AgentWatch Adversarial Harness
==============================
Multi-agent application that orchestrates attack agents against AgentWatch
and verifies detection outcomes.

Usage:
    python -m agents.harness.runner
    python -m agents.harness.runner --attack minja
    python -m agents.harness.runner --attack all --json

Exit code: 0 if all pass, 1 if any miss or unexpected FP.
"""
import asyncio
import argparse
import json
import sys
from typing import Callable, Awaitable

from agents.harness.verifier import verify, VerificationResult
from agents.harness.attacks import (
    minja,
    spyware,
    silent_loop,
    coord_failure,
    policy_bypass,
    content_injection,
)

# Registry: (name, coro_factory, expected_detected)
ATTACKS: list[tuple[str, Callable[[], Awaitable[dict]], bool]] = [
    ("minja",             minja.run,             True),
    ("spyware",           spyware.run,           True),
    ("silent_loop",       silent_loop.run,       True),
    ("coord_failure",     coord_failure.run,     True),
    ("policy_bypass",     policy_bypass.run,     True),
    ("content_injection", content_injection.run, True),
]

ATTACK_MAP = {name: (fn, expected) for name, fn, expected in ATTACKS}


async def run_attack(name: str, fn, expected: bool) -> VerificationResult:
    result = await fn()
    vr = verify(result, expected_detected=expected)
    return vr


def _fmt(vr: VerificationResult) -> str:
    icon = "✓" if vr.passed else "✗"
    status = "PASS" if vr.passed else "FAIL"
    line = f"  {icon} [{status}] {vr.attack:<22}"
    if vr.passed:
        details = []
        d = vr.details
        if "cost_anomaly_ratio" in d:
            details.append(f"ratio={d['cost_anomaly_ratio']:.1f}x")
        if "mast_category" in d:
            details.append(f"MAST-C{d['mast_category']}")
        if "attacks_caught" in d:
            details.append(f"caught={d['attacks_caught']}/{d['total_attacks']}")
            if d.get("false_positives", 0):
                details.append(f"FP={d['false_positives']}")
        if "failing_agent" in d:
            details.append(f"agent={d['failing_agent']}")
        line += "  " + " ".join(details)
    else:
        line += f"  ← {vr.failure_reason}"
    return line


async def main(attack_filter: str = "all", output_json: bool = False) -> int:
    if attack_filter == "all":
        selected = ATTACKS
    elif attack_filter in ATTACK_MAP:
        fn, expected = ATTACK_MAP[attack_filter]
        selected = [(attack_filter, fn, expected)]
    else:
        print(f"Unknown attack: {attack_filter}. Valid: {', '.join(ATTACK_MAP)}", file=sys.stderr)
        return 2

    print("AgentWatch Adversarial Harness")
    print("=" * 50)

    results = []
    for name, fn, expected in selected:
        print(f"  Running {name}...", end="", flush=True)
        vr = await run_attack(name, fn, expected)
        results.append(vr)
        print(f"\r{_fmt(vr)}")

    passed = sum(1 for r in results if r.passed)
    total = len(results)
    missed = [r for r in results if not r.passed and r.expected_detected]
    fps = [r for r in results if not r.passed and not r.expected_detected]

    print("=" * 50)
    print(f"  Result: {passed}/{total} passed", end="")
    if missed:
        print(f"  |  MISSED: {', '.join(r.attack for r in missed)}", end="")
    if fps:
        print(f"  |  FALSE-POS: {', '.join(r.attack for r in fps)}", end="")
    print()

    if output_json:
        output = {
            "passed": passed,
            "total": total,
            "results": [
                {
                    "attack": r.attack,
                    "passed": r.passed,
                    "detected": r.actual_detected,
                    "details": r.details,
                    "failure": r.failure_reason,
                }
                for r in results
            ],
        }
        print(json.dumps(output, indent=2))

    return 0 if passed == total else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AgentWatch Adversarial Harness")
    parser.add_argument("--attack", default="all",
                        help=f"Attack to run: all | {' | '.join(ATTACK_MAP)}")
    parser.add_argument("--json", action="store_true", dest="output_json",
                        help="Output JSON results")
    args = parser.parse_args()

    code = asyncio.run(main(attack_filter=args.attack, output_json=args.output_json))
    sys.exit(code)
