"""CLI commands for managing OpenAI evals integration."""

import argparse
import json
import sys

from .eval_workflow_integration import EvalWorkflowManager
from .evals_integration import (
    DEFAULT_GOLDEN_EXAMPLES,
    ConnectorReadinessEvaluator,
    create_test_data_jsonl,
)


def create_eval_definition_command(args):
    """Create an OpenAI eval definition."""
    evaluator = ConnectorReadinessEvaluator()

    try:
        eval_id = evaluator.create_eval_definition(
            eval_name=args.name, description=args.description
        )
        print(f"✅ Created eval definition: {eval_id}")
        return 0
    except Exception as e:
        print(f"❌ Failed to create eval definition: {e}")
        return 1


def create_test_data_command(args):
    """Create JSONL test data from golden examples."""
    try:
        create_test_data_jsonl(golden_examples=DEFAULT_GOLDEN_EXAMPLES, output_path=args.output)
        print(f"✅ Created test data: {args.output}")
        return 0
    except Exception as e:
        print(f"❌ Failed to create test data: {e}")
        return 1


def run_evaluation_command(args):
    """Run evaluation on a readiness report."""
    manager = EvalWorkflowManager()

    try:
        evaluation_result = manager.run_evaluation(api_name=args.api_name, trace_id=args.trace_id)

        if evaluation_result:
            summary = manager.generate_evaluation_summary(evaluation_result)
            print(summary)

            if args.output:
                with open(args.output, "w") as f:
                    json.dump(evaluation_result, f, indent=2, default=str)
                print(f"\n📄 Detailed results saved to: {args.output}")

            return 0
        else:
            print("❌ Evaluation failed - no readiness report found or evaluation error")
            return 1

    except Exception as e:
        print(f"❌ Evaluation failed: {e}")
        return 1


def list_golden_examples_command(args):
    """List available golden examples."""
    print("📋 Available Golden Examples:")
    print("=" * 50)

    for i, golden in enumerate(DEFAULT_GOLDEN_EXAMPLES, 1):
        print(f"\n{i}. {golden.api_name}")
        print(f"   Description: {golden.description}")
        print(f"   Expected Streams: {', '.join(golden.expected_streams)}")
        print(f"   Min Records: {golden.min_records_per_stream}")
        print(f"   Max Warnings: {golden.max_acceptable_warnings}")

    return 0


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="OpenAI Evals integration for connector readiness evaluation"
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    create_eval_parser = subparsers.add_parser(
        "create-eval", help="Create an OpenAI eval definition"
    )
    create_eval_parser.add_argument(
        "--name", default="connector-readiness-evaluation", help="Name for the eval definition"
    )
    create_eval_parser.add_argument(
        "--description",
        default="Evaluates connector readiness reports against golden examples",
        help="Description for the eval definition",
    )
    create_eval_parser.set_defaults(func=create_eval_definition_command)

    test_data_parser = subparsers.add_parser(
        "create-test-data", help="Create JSONL test data from golden examples"
    )
    test_data_parser.add_argument(
        "--output", default="eval_test_data.jsonl", help="Output path for JSONL test data"
    )
    test_data_parser.set_defaults(func=create_test_data_command)

    eval_parser = subparsers.add_parser("evaluate", help="Run evaluation on readiness report")
    eval_parser.add_argument("--api-name", help="API name for golden example selection")
    eval_parser.add_argument("--trace-id", help="Trace ID for correlation")
    eval_parser.add_argument("--output", help="Output path for detailed results JSON")
    eval_parser.set_defaults(func=run_evaluation_command)

    list_parser = subparsers.add_parser("list-golden", help="List available golden examples")
    list_parser.set_defaults(func=list_golden_examples_command)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
