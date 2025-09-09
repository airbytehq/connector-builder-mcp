# Copyright (c) 2025 Airbyte, Inc., all rights reserved.
"""Demo script showing how to use different agent frameworks with connector-builder-mcp.

This script demonstrates connecting to connector-builder-mcp via STDIO transport and using
the `openai-agents` library with MCP.

Usage:
    # To just test with all the defaults:
    uv run --project=examples examples/run_mcp_agent.py

    # Sending a custom prompt:
    uv run --project=examples examples/run_mcp_agent.py "Build a connector for the JSONPlaceholder API"
    uv run --project=examples examples/run_mcp_agent.py "Build a connector for Rick and Morty"
    uv run --project=examples examples/run_mcp_agent.py "Hubspot API"

    # As a poe task:
    poe run-agent "Your prompt string here"

Requirements:
    - OpenAI API key (OPENAI_API_KEY in a local '.env')
"""

import argparse
import asyncio
import os
import sys
import time
from contextlib import suppress
from functools import lru_cache
from pathlib import Path

from agents import Agent as OpenAIAgent
from agents import Runner, SQLiteSession, gen_trace_id, set_default_openai_client, trace
from agents.mcp import MCPServer, MCPServerStdio, MCPServerStdioParams

# from agents import OpenAIConversationsSession
from dotenv import load_dotenv
from openai import AsyncOpenAI


GH_MODELS_OPEANAI_API_ROOT = "https://models.github.ai/inference"

# Initialize env vars:
load_dotenv()

MAX_CONNECTOR_BUILD_STEPS = 100
DEFAULT_CONNECTOR_BUILD_API_NAME: str = "JSONPlaceholder API"
SESSION_ID: str = f"builder-mcp-session-{int(time.time())}"
WORKSPACE_WRITE_DIR: Path = Path() / "ai-generated-files" / SESSION_ID
WORKSPACE_WRITE_DIR.mkdir(parents=True, exist_ok=True)
DEFAULT_LLM_MODEL: str = "o4-mini"  # "gpt-4o-mini"
AUTO_OPEN_TRACE_URL: bool = os.environ.get("AUTO_OPEN_TRACE_URL", "1").lower() in {"1", "true"}

HEADLESS_BROWSER = True

MCP_SERVERS: list[MCPServer] = [
    MCPServerStdio(
        # This should run from the local dev environment:
        name="airbyte-connector-builder-mcp",
        params=MCPServerStdioParams(
            command="uv",
            args=[
                "run",
                "airbyte-connector-builder-mcp",
            ],
            env={},
        ),
        cache_tools_list=True,
    ),
    MCPServerStdio(
        name="playwright-web-browser",
        params=MCPServerStdioParams(
            command="npx",
            args=[
                "@playwright/mcp@latest",
                *(["--headless"] if HEADLESS_BROWSER else []),
            ],
            env={},
        ),
        cache_tools_list=True,
        # Default 5s timeout is too short.
        # - https://github.com/modelcontextprotocol/python-sdk/issues/407
        client_session_timeout_seconds=15,
    ),
    MCPServerStdio(
        name="agent-workspace-filesystem",
        params=MCPServerStdioParams(
            command="npx",
            args=[
                "mcp-server-filesystem",
                str(WORKSPACE_WRITE_DIR.absolute()),
            ],
            env={},
        ),
        cache_tools_list=True,
    ),
]


if "OPENAI_API_ROOT" in os.environ:
    openai_api_root: str = os.environ["OPENAI_API_ROOT"]
    if "github.ai" in openai_api_root and openai_api_root != GH_MODELS_OPEANAI_API_ROOT:
        print(
            f"⚠️ Warning: Detected GitHub Models endpoint but non-standard API root: {openai_api_root}. "
            f"Recommended root URL is: {GH_MODELS_OPEANAI_API_ROOT}"
        )

    if openai_api_root.lower() in {"gh", "github", "github models"}:
        print(
            f"Found GitHub Models endpoint alias: {openai_api_root}. "
            f"Applying recommended Github Models URL root: {GH_MODELS_OPEANAI_API_ROOT}"
        )
        openai_api_root = GH_MODELS_OPEANAI_API_ROOT

    if "github.ai" in openai_api_root and "OPENAI_API_KEY" not in os.environ:
        print(
            "GitHub Models endpoint detected but not API Root is set. "
            "Attempting to extract token using `gh auth token` CLI command."
        )
        import subprocess

        _ = subprocess.check_output(["gh", "auth", "status"])
        openai_api_key: str = (
            subprocess.check_output(["gh", "auth", "token"]).decode("utf-8").strip()
        )
        print(
            "✅ Successfully extracted GitHub token from `gh` CLI: "
            f"({openai_api_key[:4]}...{openai_api_key[-4:]})"
        )
        if not openai_api_key.startswith("sk-"):
            raise ValueError(
                "Extracted GitHub token does not appear to be valid. "
                "Please ensure you have the GitHub CLI installed and authenticated."
            )
        os.environ["OPENAI_API_KEY"] = openai_api_key

    print(f"ℹ️ Using Custom OpenAI-Compatible LLM Endpoint: {openai_api_root}")
    github_models_client = AsyncOpenAI(
        base_url=openai_api_root,
        api_key=os.environ.get("OPENAI_API_KEY", None),
    )
    set_default_openai_client(
        github_models_client,
        use_for_tracing=True,
    )


@lru_cache  # Hacky way to run 'just once' 🙂
def _open_if_browser_available(url: str) -> None:
    """Open a URL for the user to track progress.

    Fail gracefully in the case that we don't have a browser.
    """
    if AUTO_OPEN_TRACE_URL is False:
        return

    with suppress(Exception):
        import webbrowser  # noqa: PLC0415

        webbrowser.open(url=url)


async def run_connector_build(
    api_name: str | None = None,
    instructions: str | None = None,
    model: str = DEFAULT_LLM_MODEL,
    *,
    headless: bool = False,
) -> None:
    """Run an agentic AI connector build session."""
    if not api_name and not instructions:
        raise ValueError("Either api_name or instructions must be provided.")
    if api_name:
        instructions = (
            f"Fully build and test a connector for '{api_name}'. " + (instructions or "")
        ).strip()
    assert instructions, "By now, instructions should be non-null."

    print("\n🤖 Building Connector using AI", flush=True)
    print("=" * 30, flush=True)
    print(f"USER PROMPT: {instructions}", flush=True)
    print("=" * 30, flush=True)

    repo_root = Path(__file__).parent.parent
    prompt_file = (
        repo_root / "prompts" / ("root-prompt-headless.md" if headless else "root-prompt.md")
    )
    prompt = prompt_file.read_text(encoding="utf-8") + "\n\n"
    prompt += instructions
    await run_agent_prompt(
        prompt=prompt,
        model=model,
    )


async def run_agent_prompt(
    prompt: str,
    model: str,
) -> None:
    """Run the agent using a given prompt."""
    # session = OpenAIConversationsSession()  # Not able to import this for some reason
    session = SQLiteSession(session_id=SESSION_ID)
    agent = OpenAIAgent(
        name="MCP Connector Builder",
        instructions=(
            "You are a helpful assistant with access to MCP tools for building Airbyte connectors."
        ),
        mcp_servers=MCP_SERVERS,
        model=model,
    )

    for server in MCP_SERVERS:
        await server.connect()

    trace_id = gen_trace_id()
    with trace(workflow_name="Connector Builder Session", trace_id=trace_id):
        trace_url = f"https://platform.openai.com/traces/trace?trace_id={trace_id}"

        # Start with the full prompt as input. Next iterations will apply user input.
        input_prompt: str = prompt
        while True:
            print("\n⚙️  AI Agent is working...", flush=True)
            print(f"🔗 Follow along at: {trace_url}")
            _open_if_browser_available(trace_url)
            try:
                response = await Runner.run(
                    starting_agent=agent,
                    input=input_prompt,
                    max_turns=100,
                    session=session,
                )
                print("\n🤖  AI Agent: ", end="", flush=True)
                print(response.final_output)

                input_prompt = input("\n👤  You: ")
                if input_prompt.lower() in {"exit", "quit"}:
                    print("☑️ Ending conversation...")
                    print(f"🪵 Review trace logs at: {trace_url}")
                    break

            except KeyboardInterrupt:
                print("\n🛑 Conversation terminated (ctrl+c input received).", flush=True)
                print(f"🪵 Review trace logs at: {trace_url}", flush=True)
                sys.exit(0)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run MCP agent with a prompt.",
    )
    parser.add_argument(
        "prompt",
        nargs="?",
        default=DEFAULT_CONNECTOR_BUILD_API_NAME,
        help="Prompt string to pass to the agent.",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run in headless mode without user interaction.",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_LLM_MODEL,
        help=(
            "".join([
                "LLM model to use for the agent. ",
                "Examples: o4-mini, gpt-4o-mini. ",
                f"Default: {DEFAULT_LLM_MODEL}",
            ])
        ),
    )
    return parser.parse_args()


async def main() -> None:
    """Run all demo scenarios."""
    print("🚀 Multi-Framework MCP + connector-builder-mcp Integration Demo")
    print("=" * 60)
    print()
    print("This demo shows how different agent frameworks can wrap connector-builder-mcp")
    print("to provide vendor-neutral access to Airbyte connector development tools.")
    print()

    cli_args: argparse.Namespace = _parse_args()

    await run_connector_build(
        instructions=cli_args.prompt,
        headless=cli_args.headless,
        model=cli_args.model,
    )

    print("\n" + "=" * 60)
    print("✨ Execution completed!")


if __name__ == "__main__":
    asyncio.run(main())
