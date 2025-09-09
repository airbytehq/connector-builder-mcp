# Copyright (c) 2025 Airbyte, Inc., all rights reserved.
"""Example execution script for agentic connector building.

This script automatically chooses between single-agent (interactive) and manager-developer
(headless) architectures based on the execution mode. It demonstrates connecting to
connector-builder-mcp via STDIO transport and using the `openai-agents` library with MCP.

Usage:
    uv run --project=examples examples/run_mcp_agent.py
    uv run --project=examples examples/run_mcp_agent.py "Build a connector for the JSONPlaceholder API"

    uv run --project=examples examples/run_mcp_agent.py --headless "Build a connector for the JSONPlaceholder API"

    poe run-connector-build "Your prompt string here"
    poe run-connector-build "Your API name"

    # Interactively:
    poe run-connector-build-interactive "Your API name"

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

from agents import (
    Agent,
    Runner,
    SQLiteSession,
    gen_trace_id,
    handoff,
    set_default_openai_api,
    set_default_openai_client,
    set_tracing_disabled,
    trace,
)
from agents import Agent as OpenAIAgent
from agents.mcp import (
    MCPServer,
    MCPServerStdio,
    MCPServerStdioParams,
)

# from agents import OpenAIConversationsSession
from dotenv import load_dotenv
from openai import AsyncOpenAI
from pydantic import BaseModel


GH_MODELS_OPENAI_BASE_URL: str = "https://models.github.ai/inference"
OPENAI_BASE_URL_ENV_VAR: str = "OPENAI_BASE_URL"
OPENAI_API_KEY_ENV_VAR: str = "OPENAI_API_KEY"

# Initialize env vars:
load_dotenv()


class Phase1Data(BaseModel):
    """Data for Phase 1: First successful stream read."""

    api_name: str
    additional_instructions: str = ""
    phase_description: str = "Phase 1: First Successful Stream Read"
    objectives: list[str] = [
        "Research the target API and understand its structure",
        "Create initial manifest using the scaffold tool",
        "Set up proper authentication (request secrets from user if needed)",
        "Configure one stream without pagination initially",
        "Validate that you can read records from this stream",
    ]


class Phase2Data(BaseModel):
    """Data for Phase 2: Working pagination."""

    api_name: str
    phase_description: str = "Phase 2: Working Pagination"
    objectives: list[str] = [
        "Add pagination configuration to the manifest",
        "Test reading multiple pages of data",
        "Confirm you can reach the end of the stream",
        "Verify record counts are not suspicious multiples",
        "Update checklist.md with progress",
    ]


class Phase3Data(BaseModel):
    """Data for Phase 3: Add remaining streams."""

    api_name: str
    phase_description: str = "Phase 3: Add Remaining Streams"
    objectives: list[str] = [
        "Identify all available streams from API documentation",
        "Add each stream to the manifest one by one",
        "Test each stream individually",
        "Run full connector readiness test",
        "Update checklist.md with final results",
    ]


MAX_CONNECTOR_BUILD_STEPS = 100
DEFAULT_CONNECTOR_BUILD_API_NAME: str = "JSONPlaceholder API"
SESSION_ID: str = f"unified-mcp-session-{int(time.time())}"
WORKSPACE_WRITE_DIR: Path = Path() / "ai-generated-files" / SESSION_ID
WORKSPACE_WRITE_DIR.mkdir(parents=True, exist_ok=True)
DEFAULT_LLM_MODEL: str = "openai/gpt-4o-mini"  # "gpt-4o-mini"
AUTO_OPEN_TRACE_URL: bool = os.environ.get("AUTO_OPEN_TRACE_URL", "1").lower() in {"1", "true"}

HEADLESS_BROWSER = True

MCP_CONNECTOR_BUILDER_TOOL = lambda: MCPServerStdio(  # noqa: E731
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
)
MCP_PLAYWRIGHT_WEB_BROWSER = lambda: MCPServerStdio(  # noqa: E731
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
)
MCP_FILESYSTEM_SERVER = lambda: MCPServerStdio(  # noqa: E731
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
)
ALL_MCP_SERVERS: list[MCPServer] = [
    MCP_CONNECTOR_BUILDER_TOOL(),
    MCP_PLAYWRIGHT_WEB_BROWSER(),
    MCP_FILESYSTEM_SERVER(),
]
MANAGER_AGENT_TOOLS: list[MCPServer] = [
    MCP_FILESYSTEM_SERVER(),
]
DEVELOPER_AGENT_TOOLS: list[MCPServer] = [
    MCP_PLAYWRIGHT_WEB_BROWSER(),
    MCP_CONNECTOR_BUILDER_TOOL(),
    MCP_FILESYSTEM_SERVER(),
]


if OPENAI_BASE_URL_ENV_VAR in os.environ:
    print("⚙️ Detected custom OpenAI API root in environment.")
    OPENAI_BASE_URL_ENV_VAR: str = os.environ[OPENAI_BASE_URL_ENV_VAR]
    if (
        "github.ai" in OPENAI_BASE_URL_ENV_VAR
        and OPENAI_BASE_URL_ENV_VAR != GH_MODELS_OPENAI_BASE_URL
    ):
        print(
            f"⚠️ Warning: Detected GitHub Models endpoint but non-standard API root: {OPENAI_BASE_URL_ENV_VAR}. "
            f"Recommended root URL is: {GH_MODELS_OPENAI_BASE_URL}"
        )

    if OPENAI_BASE_URL_ENV_VAR.lower() in {"gh", "github", "github models"}:
        print(
            f"Found GitHub Models endpoint alias: {OPENAI_BASE_URL_ENV_VAR}. "
            f"Applying recommended Github Models URL root: {GH_MODELS_OPENAI_BASE_URL}"
        )
        OPENAI_BASE_URL_ENV_VAR = GH_MODELS_OPENAI_BASE_URL

    if "github.ai" in OPENAI_BASE_URL_ENV_VAR and "OPENAI_API_KEY" not in os.environ:
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

    print(f"ℹ️ Using Custom OpenAI-Compatible LLM Endpoint: {OPENAI_BASE_URL_ENV_VAR}")
    github_models_client = AsyncOpenAI(
        base_url=OPENAI_BASE_URL_ENV_VAR,
        api_key=os.environ.get("OPENAI_API_KEY", None),
    )
    set_default_openai_client(
        github_models_client,
        use_for_tracing=False,
    )
    set_default_openai_api("chat_completions")  # GH Models doesn't support 'responses' endpoint.
    set_tracing_disabled(True)  # Tracing not supported with GitHub Models endpoint.


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


def create_developer_agent(session_id: str, model: str) -> OpenAIAgent:
    """Create the developer agent that executes specific phases."""
    return OpenAIAgent(
        name="MCP Connector Developer",
        instructions=(
            "You are a specialized developer agent that executes specific phases of Airbyte connector building. "
            "You work under the coordination of a manager agent and focus on implementing the technical details "
            "of connector development using MCP tools. Follow the provided phase instructions precisely. "
            "Always update checklist.md as you complete each step."
        ),
        mcp_servers=DEVELOPER_AGENT_TOOLS,
        model=model,
    )


def create_manager_agent(developer_agent: OpenAIAgent, session_id: str, model: str) -> OpenAIAgent:
    """Create the manager agent that orchestrates the 3-phase workflow."""

    async def on_phase1_handoff(ctx, input_data: Phase1Data):
        print(f"🚀 Starting {input_data.phase_description} for {input_data.api_name}")

    async def on_phase2_handoff(ctx, input_data: Phase2Data):
        print(f"🔄 Starting {input_data.phase_description} for {input_data.api_name}")

    async def on_phase3_handoff(ctx, input_data: Phase3Data):
        print(f"🎯 Starting {input_data.phase_description} for {input_data.api_name}")

    return OpenAIAgent(
        name="MCP Connector Manager",
        instructions=(
            "You are a manager agent that orchestrates connector building by delegating "
            "work to a developer agent across 3 phases: stream read, pagination, remaining streams. "
            "Monitor progress and ensure each phase completes successfully before moving to the next. "
            "Use the handoff tools to delegate specific phases to the developer agent."
        ),
        handoffs=[
            handoff(
                agent=developer_agent,
                tool_name_override="start_phase_1_stream_read",
                tool_description_override="Start Phase 1: First successful stream read",
                input_type=Phase1Data,
                on_handoff=on_phase1_handoff,
            ),
            handoff(
                agent=developer_agent,
                tool_name_override="start_phase_2_pagination",
                tool_description_override="Start Phase 2: Working pagination",
                input_type=Phase2Data,
                on_handoff=on_phase2_handoff,
            ),
            handoff(
                agent=developer_agent,
                tool_name_override="start_phase_3_remaining_streams",
                tool_description_override="Start Phase 3: Add remaining streams",
                input_type=Phase3Data,
                on_handoff=on_phase3_handoff,
            ),
        ],
        mcp_servers=MANAGER_AGENT_TOOLS,
        model=model,
    )


async def run_connector_build(
    api_name: str | None = None,
    instructions: str | None = None,
    model: str = DEFAULT_LLM_MODEL,
    *,
    headless: bool = False,
) -> None:
    """Run an agentic AI connector build session with automatic mode selection."""
    if not api_name and not instructions:
        raise ValueError("Either api_name or instructions must be provided.")
    if api_name:
        instructions = (
            f"Fully build and test a connector for '{api_name}'. " + (instructions or "")
        ).strip()
    assert instructions, "By now, instructions should be non-null."

    if headless:
        print("\n🤖 Building Connector using Manager-Developer Architecture", flush=True)
        print("=" * 60, flush=True)
        print(f"API: {api_name or 'N/A'}")
        print(f"USER PROMPT: {instructions}", flush=True)
        print("=" * 60, flush=True)
        await run_manager_developer_build(
            api_name=api_name,
            instructions=instructions,
            model=model,
        )
    else:
        print("\n🤖 Building Connector using Interactive AI", flush=True)
        print("=" * 30, flush=True)
        print(f"API: {api_name or 'N/A'}")
        print(f"USER PROMPT: {instructions}", flush=True)
        print("=" * 30, flush=True)
        prompt_file = Path("./prompts") / "root-prompt.md"
        prompt = prompt_file.read_text(encoding="utf-8") + "\n\n"
        prompt += instructions
        await run_interactive_build(
            prompt=prompt,
            model=model,
        )


async def run_interactive_build(
    prompt: str,
    model: str,
) -> None:
    """Run the agent using interactive mode with conversation loop."""
    session = SQLiteSession(session_id=SESSION_ID)
    agent = Agent(
        name="MCP Connector Builder",
        instructions=(
            "You are a helpful assistant with access to MCP tools for building Airbyte connectors."
        ),
        mcp_servers=ALL_MCP_SERVERS,
        model=model,
    )

    for server in ALL_MCP_SERVERS:
        await server.connect()

    trace_id = gen_trace_id()
    with trace(workflow_name="Interactive Connector Builder Session", trace_id=trace_id):
        trace_url = f"https://platform.openai.com/traces/trace?trace_id={trace_id}"

        input_prompt: str = prompt
        while True:
            print("\n⚙️  AI Agent is working...", flush=True)
            print(f"🔗 Follow along at: {trace_url}")
            _open_if_browser_available(trace_url)
            try:
                # Kick off the streaming execution
                result_stream = Runner.run_streamed(
                    starting_agent=agent,
                    input=input_prompt,
                    max_turns=100,
                    session=session,
                )

                # Iterate through events as they arrive
                async for event in result_stream.stream_events():
                    if event.type in {"tool_start", "tool_end", "agent_action"}:
                        print(
                            f"[{event.name if hasattr(event, 'name') else event.type}] {str(event)[:120]}...",
                            flush=True,
                        )
                        continue

                    if event.type == "raw_response_event":
                        continue

                    print(f"[{event.type}] {str(event)[:120]}...", flush=True)

                # After streaming ends, get the final result
                print("\n🤖  AI Agent: ", end="", flush=True)
                print(result_stream.final_output)

                input_prompt = input("\n👤  You: ")
                if input_prompt.lower() in {"exit", "quit"}:
                    print("☑️ Ending conversation...")
                    print(f"🪵 Review trace logs at: {trace_url}")
                    break

            except KeyboardInterrupt:
                print("\n🛑 Conversation terminated (ctrl+c input received).", flush=True)
                print(f"🪵 Review trace logs at: {trace_url}", flush=True)
                sys.exit(0)


async def run_manager_developer_build(
    api_name: str | None = None,
    instructions: str | None = None,
    model: str = DEFAULT_LLM_MODEL,
) -> None:
    """Run a 3-phase connector build using manager-developer architecture."""
    session = SQLiteSession(session_id=SESSION_ID)

    developer_agent = create_developer_agent(SESSION_ID, model)
    manager_agent = create_manager_agent(developer_agent, SESSION_ID, model)

    for server in [*MANAGER_AGENT_TOOLS, *DEVELOPER_AGENT_TOOLS]:
        await server.connect()

    trace_id = gen_trace_id()
    with trace(workflow_name="Manager-Developer Connector Build", trace_id=trace_id):
        trace_url = f"https://platform.openai.com/traces/trace?trace_id={trace_id}"

        manager_prompt = f"""
        You are orchestrating a 3-phase connector building process for: {api_name}

        Instructions: {instructions}

        Execute the phases in order:
        1. Use start_phase_1_stream_read to delegate Phase 1 (first successful stream read)
        2. After Phase 1 completes, use start_phase_2_pagination to delegate Phase 2 (working pagination)
        3. After Phase 2 completes, use start_phase_3_remaining_streams to delegate Phase 3 (add remaining streams)

        Monitor progress and ensure each phase completes successfully before moving to the next.
        """

        print("\n⚙️  Manager Agent is orchestrating the build...", flush=True)
        print(f"🔗 Follow along at: {trace_url}")
        _open_if_browser_available(trace_url)

        try:
            response = await Runner.run(
                starting_agent=manager_agent,
                input=manager_prompt,
                max_turns=MAX_CONNECTOR_BUILD_STEPS,
                session=session,
            )
            print("\n🤖  Manager Agent: ", end="", flush=True)
            print(response.final_output)

        except KeyboardInterrupt:
            print("\n🛑 Build terminated (ctrl+c input received).", flush=True)
            print(f"🪵 Review trace logs at: {trace_url}", flush=True)
            sys.exit(0)


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
        "--headless",
        action="store_true",
        help="Run in headless mode using manager-developer architecture.",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_LLM_MODEL,
        help=(
            "".join(
                [
                    "LLM model to use for the agent. ",
                    "Examples: o4-mini, gpt-4o-mini. ",
                    f"Default: {DEFAULT_LLM_MODEL}",
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
        headless=cli_args.headless,
        model=cli_args.model,
    )

    print("\n" + "=" * 60)
    print("✨ Execution completed!")


if __name__ == "__main__":
    asyncio.run(main())
