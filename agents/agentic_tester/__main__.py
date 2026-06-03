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
  python -m agents.agentic_tester --mock                   # no API key needed
  python -m agents.agentic_tester --mock --verbose
  python -m agents.agentic_tester --mock --save-report docs/TESTING_GAPS.md
  LLM_API_KEY=sk-... python -m agents.agentic_tester
  LLM_API_KEY=sk-... python -m agents.agentic_tester --output gaps/run_$(date +%Y%m%d).json
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
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Run without LLM_API_KEY using curated mock payloads",
    )

    args = parser.parse_args()

    try:
        code = asyncio.run(run(
            verbose=args.verbose,
            output_json=args.output,
            save_report=args.save_report,
            mock=args.mock,
        ))
        sys.exit(code)
    except EnvironmentError as e:
        print(f"\nERROR: {e}")
        print("Set LLM_API_KEY and retry, or use --mock to run without an API key.")
        sys.exit(2)
    except KeyboardInterrupt:
        print("\nInterrupted.")
        sys.exit(130)


if __name__ == "__main__":
    main()
