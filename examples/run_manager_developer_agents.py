# Copyright (c) 2025 Airbyte, Inc., all rights reserved.
"""Manager-Developer agent architecture for connector building.

This script demonstrates the new two-agent system where a manager agent
orchestrates connector building by delegating to a developer agent across
3 phases using handoffs: stream read, pagination, remaining streams.
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
from agents import Runner, SQLiteSession, gen_trace_id, handoff, trace
from agents.mcp import MCPServer, MCPServerStdio, MCPServerStdioParams
from dotenv import load_dotenv
from pydantic import BaseModel


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
SESSION_ID: str = f"manager-dev-session-{int(time.time())}"
WORKSPACE_WRITE_DIR: Path = Path() / "ai-generated-files" / SESSION_ID
WORKSPACE_WRITE_DIR.mkdir(parents=True, exist_ok=True)
DEFAULT_LLM_MODEL: str = "o4-mini"
AUTO_OPEN_TRACE_URL: bool = os.environ.get("AUTO_OPEN_TRACE_URL", "1").lower() in {"1", "true"}

HEADLESS_BROWSER = True

MCP_SERVERS: list[MCPServer] = [
    MCPServerStdio(
        name="airbyte-connector-builder-mcp",
        params=MCPServerStdioParams(
            command="uv",
            args=["run", "airbyte-connector-builder-mcp"],
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


@lru_cache
def _open_if_browser_available(url: str) -> None:
    """Open a URL for the user to track progress."""
    if AUTO_OPEN_TRACE_URL is False:
        return

    with suppress(Exception):
        import webbrowser

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
        mcp_servers=MCP_SERVERS,
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
        mcp_servers=MCP_SERVERS,
        model=model,
    )


async def run_connector_build(
    api_name: str | None = None,
    instructions: str | None = None,
    model: str = DEFAULT_LLM_MODEL,
    *,
    headless: bool = False,
) -> None:
    """Run a 3-phase connector build using manager-developer architecture."""
    if not api_name and not instructions:
        raise ValueError("Either api_name or instructions must be provided.")
    if api_name:
        instructions = (
            f"Build a connector for '{api_name}' using the 3-phase approach. "
            + (instructions or "")
        ).strip()
    assert instructions, "By now, instructions should be non-null."

    print("\n🤖 Building Connector using Manager-Developer Architecture", flush=True)
    print("=" * 60, flush=True)
    print(f"API: {api_name}")
    print(f"USER PROMPT: {instructions}", flush=True)
    print("=" * 60, flush=True)

    session = SQLiteSession(session_id=SESSION_ID)

    developer_agent = create_developer_agent(SESSION_ID, model)

    manager_agent = create_manager_agent(developer_agent, SESSION_ID, model)

    for server in MCP_SERVERS:
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
        description="Run manager-developer agents for connector building.",
    )
    parser.add_argument(
        "prompt",
        nargs="?",
        default=DEFAULT_CONNECTOR_BUILD_API_NAME,
        help="API name or prompt string to pass to the agents.",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run in headless mode without user interaction.",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_LLM_MODEL,
        help=f"LLM model to use. Default: {DEFAULT_LLM_MODEL}",
    )
    return parser.parse_args()


async def main() -> None:
    """Run the manager-developer agent demo."""
    print("🚀 Manager-Developer Agent Architecture Demo")
    print("=" * 60)
    print()
    print("This demo shows how a manager agent orchestrates connector building")
    print("by delegating to a developer agent across 3 phases using handoffs.")
    print()

    cli_args: argparse.Namespace = _parse_args()

    await run_connector_build(
        instructions=cli_args.prompt,
        headless=cli_args.headless,
        model=cli_args.model,
    )

    print("\n" + "=" * 60)
    print("✨ Manager-Developer execution completed!")


if __name__ == "__main__":
    asyncio.run(main())
