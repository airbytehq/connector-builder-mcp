# Copyright (c) 2025 Airbyte, Inc., all rights reserved.
"""CLI for running connector builder agents.

The CLI offers single-agent (interactive) and manager-developer
(headless) architectures based on the execution mode. It demonstrates connecting to
connector-builder-mcp via STDIO transport and using the `openai-agents` library with MCP.

Usage:
    poe build-connector "Your prompt string here"
    poe build-connector "Your API name"

    # Interactively:
    poe build-connector-interactive "Your API name"

Requirements:
    - OpenAI API key (OPENAI_API_KEY in a local '.env')
"""

import argparse
import asyncio

# from agents import OpenAIConversationsSession
from .constants import (
    DEFAULT_CONNECTOR_BUILD_API_NAME,
    DEFAULT_DEVELOPER_MODEL,
    DEFAULT_MANAGER_MODEL,
)
from .run import (
    run_connector_build,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run unified MCP agent with automatic mode selection.",
    )
    parser.add_argument(
        "prompt",
        nargs="?",
        default=DEFAULT_CONNECTOR_BUILD_API_NAME,
        help="API name or prompt string to pass to the agent.",
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Run in interactive mode (bypass manager-developer multi-agent orchestration).",
    )
    parser.add_argument(
        "--developer-model",
        default=DEFAULT_DEVELOPER_MODEL,
        help=(
            "".join(
                [
                    "LLM model to use for the agent. ",
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
                    "LLM model to use for the agent. ",
                    "Examples: o4-mini, gpt-4o-mini. ",
                    f"Default: {DEFAULT_MANAGER_MODEL}",
                ]
            )
        ),
    )
    return parser.parse_args()


async def main() -> None:
    """Run all demo scenarios."""
    print("🚀 AI Connector Builder MCP Integration Demo")
    print("=" * 60)
    print()
    print("This demo shows how agents can wrap connector-builder-mcp")
    print("to provide access to Airbyte connector development tools.")
    print()

    cli_args: argparse.Namespace = _parse_args()

    await run_connector_build(
        instructions=cli_args.prompt,
        interactive=cli_args.interactive,
        developer_model=cli_args.developer_model,
        manager_model=cli_args.manager_model,
    )

    print("\n" + "=" * 60)
    print("✨ Execution completed!")


if __name__ == "__main__":
    asyncio.run(main())
