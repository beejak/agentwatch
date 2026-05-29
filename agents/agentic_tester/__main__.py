"""CLI entry point: python -m agents.agentic_tester"""
import argparse
import asyncio
import sys

from agents.agentic_tester.orchestrator import run


def main():
    parser = argparse.ArgumentParser(
        description="AgentWatch Agentic Tester — LLM-driven adversarial probing",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m agents.agentic_tester
  python -m agents.agentic_tester --verbose
  python -m agents.agentic_tester --save-report docs/TESTING_GAPS.md
  python -m agents.agentic_tester --output gaps/run_$(date +%Y%m%d).json
  ANTHROPIC_API_KEY=sk-... python -m agents.agentic_tester
        """,
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show per-payload results during execution",
    )
    parser.add_argument(
        "--output", "-o",
        metavar="FILE.json",
        help="Save full results as JSON",
    )
    parser.add_argument(
        "--save-report", "-r",
        metavar="FILE.md",
        help="Save gap analysis as Markdown (e.g. docs/TESTING_GAPS.md)",
    )

    args = parser.parse_args()

    try:
        code = asyncio.run(run(
            verbose=args.verbose,
            output_json=args.output,
            save_report=args.save_report,
        ))
        sys.exit(code)
    except EnvironmentError as e:
        print(f"\nERROR: {e}")
        print("Set ANTHROPIC_API_KEY and retry.")
        sys.exit(2)
    except KeyboardInterrupt:
        print("\nInterrupted.")
        sys.exit(130)


if __name__ == "__main__":
    main()
