# Copyright (c) 2025 Airbyte, Inc., all rights reserved.
"""CLI for running connector builder evaluations.

Usage:
    poe build-connector-evals
    poe build-connector-evals --config-path evals/my-connectors.yaml
    poe build-connector-evals --developer-model gpt-4o --manager-model o1-mini

Requirements:
    - OpenAI API key (OPENAI_API_KEY in a local '.env')
    - YAML config file with connector names
"""

import argparse
import asyncio
from pathlib import Path

from .constants import (
    DEFAULT_DEVELOPER_MODEL,
    DEFAULT_MANAGER_MODEL,
)
from .evals import run_evaluation


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run connector builder evaluations using YAML configuration.",
    )
    parser.add_argument(
        "--config-path",
        default="connector_builder_agents/evals/connectors.yaml",
        help="Path to YAML configuration file with connector names.",
    )
    parser.add_argument(
        "--output-path",
        default="evals/results.json",
        help="Path to save evaluation results JSON file.",
    )
    parser.add_argument(
        "--developer-model",
        default=DEFAULT_DEVELOPER_MODEL,
        help=(
            "".join(
                [
                    "LLM model to use for the developer agent. ",
                    "Examples: o4-mini, gpt-4o-mini. ",
                    f"Default: {DEFAULT_DEVELOPER_MODEL}",
                ]
            )
        ),
    )
    parser.add_argument(
        "--manager-model",
        default=DEFAULT_MANAGER_MODEL,
        help=(
            "".join(
                [
                    "LLM model to use for the manager agent. ",
                    "Examples: o4-mini, gpt-4o-mini. ",
                    f"Default: {DEFAULT_MANAGER_MODEL}",
                ]
            )
        ),
    )
    return parser.parse_args()


async def main() -> None:
    """Run connector builder evaluations."""
    print("🧪 Airbyte Connector Builder Evaluations")
    print("=" * 60)
    print()
    print("This tool evaluates connector builds using YAML configuration")
    print("and collects Runner.run outputs for analysis.")
    print()

    cli_args: argparse.Namespace = _parse_args()

    # Ensure config file exists
    config_path = Path(cli_args.config_path)
    if not config_path.exists():
        print(f"❌ Configuration file not found: {config_path}")
        print("Please create a YAML file with connector names like:")
        print("connectors:")
        print('  - name: "JSONPlaceholder"')
        print('  - name: "GitHub"')
        return

    # Ensure output directory exists
    output_path = Path(cli_args.output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    await run_evaluation(
        config_path=cli_args.config_path,
        output_path=cli_args.output_path,
        developer_model=cli_args.developer_model,
        manager_model=cli_args.manager_model,
    )

    print("\n" + "=" * 60)
    print("✨ Evaluation completed!")


if __name__ == "__main__":
    asyncio.run(main())
