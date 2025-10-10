# Copyright (c) 2025 Airbyte, Inc., all rights reserved.
"""Functions to run connector builder agents in different modalities."""

import sys
import time
from pathlib import Path

from agents import (
    Agent,
    Runner,
    SQLiteSession,
    gen_trace_id,
    trace,
)
from agents.result import RunResult

# from agents import OpenAIConversationsSession
from ._util import get_secrets_dotenv, open_if_browser_available
from .agents import (
    add_handback_to_manager,
    create_developer_agent,
    create_manager_agent,
)
from .constants import (
    DEFAULT_DEVELOPER_MODEL,
    DEFAULT_MANAGER_MODEL,
    MAX_CONNECTOR_BUILD_STEPS,
)
from .tools import (
    create_session_mcp_servers,
    create_session_state,
    is_complete,
    update_progress_log,
)


def generate_session_id() -> str:
    """Generate a unique session ID based on current timestamp."""
    return f"unified-mcp-session-{int(time.time())}"


def get_workspace_dir(session_id: str) -> Path:
    """Get workspace directory path for a given session ID."""
    workspace_dir = Path() / "ai-generated-files" / session_id
    workspace_dir.mkdir(parents=True, exist_ok=True)
    return workspace_dir


async def run_connector_build(
    api_name: str | None = None,
    instructions: str | None = None,
    developer_model: str = DEFAULT_DEVELOPER_MODEL,
    manager_model: str = DEFAULT_MANAGER_MODEL,
    existing_connector_name: str | None = None,
    existing_config_name: str | None = None,
    *,
    interactive: bool = False,
    session_id: str | None = None,
) -> list[RunResult] | None:
    """Run an agentic AI connector build session with automatic mode selection."""
    if not api_name and not instructions:
        raise ValueError("Either api_name or instructions must be provided.")

    if api_name:
        instructions = (
            f"Fully build and test a connector for '{api_name}'. \n" + (instructions or "")
        ).strip()
    assert instructions, "By now, instructions should be non-null."
    if existing_connector_name and existing_config_name:
        dotenv_path = get_secrets_dotenv(
            existing_connector_name=existing_connector_name,
            existing_config_name=existing_config_name,
        )
        if dotenv_path:
            print(f"🔐 Using secrets dotenv: {dotenv_path}")
            instructions += (
                f"\nSecrets dotenv file '{dotenv_path.resolve()!s}' contains necessary credentials "
                "and can be passed to your tools. Start by using the 'list_dotenv_secrets' tool "
                "to list available config values within that file. You will need to name the "
                "config values exactly as they appear in the dotenv file."
            )

    # Generate session_id if not provided
    if session_id is None:
        session_id = generate_session_id()

    if not interactive:
        print("\n🤖 Building Connector using Manager-Developer Architecture", flush=True)
        print("=" * 60, flush=True)
        print(f"API: {api_name or 'N/A'}")
        print(f"USER PROMPT: {instructions}", flush=True)
        print("=" * 60, flush=True)
        results = await run_manager_developer_build(
            api_name=api_name,
            instructions=instructions,
            developer_model=developer_model,
            manager_model=manager_model,
            session_id=session_id,
        )
        return results
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
            model=developer_model,
            session_id=session_id,
        )
        return None


async def run_interactive_build(
    prompt: str,
    model: str,
    session_id: str,
) -> None:
    """Run the agent using interactive mode with conversation loop."""
    # Create workspace directory and session state
    workspace_dir = get_workspace_dir(session_id)
    session_state = create_session_state(workspace_dir)

    session = SQLiteSession(session_id=session_id)
    all_mcp_servers, _, _ = create_session_mcp_servers(session_state)
    agent = Agent(
        name="MCP Connector Builder",
        instructions=(
            "You are a helpful assistant with access to MCP tools for building Airbyte connectors."
        ),
        mcp_servers=all_mcp_servers,
        model=model,
    )

    for server in all_mcp_servers:
        await server.connect()

    trace_id = gen_trace_id()
    with trace(workflow_name="Interactive Connector Builder Session", trace_id=trace_id):
        trace_url = f"https://platform.openai.com/traces/trace?trace_id={trace_id}"

        input_prompt: str = prompt
        while True:
            update_progress_log("\n⚙️  AI Agent is working...", session_state)
            update_progress_log(f"🔗 Follow along at: {trace_url}", session_state)
            open_if_browser_available(trace_url)
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
                        update_progress_log(
                            f"[{event.name if hasattr(event, 'name') else event.type}] {str(event)[:120]}...",
                            session_state,
                        )
                        continue

                    if event.type == "raw_response_event":
                        continue

                    update_progress_log(f"[{event.type}] {str(event)[:120]}...", session_state)

                # After streaming ends, get the final result
                update_progress_log(f"\n🤖  AI Agent: {result_stream.final_output}", session_state)

                input_prompt = input("\n👤  You: ")
                if input_prompt.lower() in {"exit", "quit"}:
                    update_progress_log("☑️ Ending conversation...", session_state)
                    update_progress_log(f"🪵 Review trace logs at: {trace_url}", session_state)
                    break

            except KeyboardInterrupt:
                update_progress_log(
                    "\n🛑 Conversation terminated (ctrl+c input received).", session_state
                )
                update_progress_log(f"🪵 Review trace logs at: {trace_url}", session_state)
                sys.exit(0)
            finally:
                for server in all_mcp_servers:
                    await server.cleanup()

        return None


async def run_manager_developer_build(
    api_name: str | None = None,
    instructions: str | None = None,
    developer_model: str = DEFAULT_DEVELOPER_MODEL,
    manager_model: str = DEFAULT_MANAGER_MODEL,
    session_id: str | None = None,
) -> list[RunResult]:
    """Run connector build using manager-developer architecture."""
    # Generate session_id if not provided
    if session_id is None:
        session_id = generate_session_id()

    session = SQLiteSession(session_id=session_id)

    # Create workspace directory and session state
    workspace_dir = get_workspace_dir(session_id)
    session_state = create_session_state(workspace_dir)

    # Create MCP servers for this session
    all_servers, manager_servers, developer_servers = create_session_mcp_servers(session_state)

    developer_agent = create_developer_agent(
        model=developer_model,
        api_name=api_name or "(see below)",
        additional_instructions=instructions or "",
        session_state=session_state,
        mcp_servers=developer_servers,
    )
    manager_agent = create_manager_agent(
        developer_agent,
        model=manager_model,
        api_name=api_name or "(see below)",
        additional_instructions=instructions or "",
        session_state=session_state,
        mcp_servers=manager_servers,
    )
    add_handback_to_manager(
        developer_agent=developer_agent,
        manager_agent=manager_agent,
        session_state=session_state,
    )

    for server in all_servers:
        print(f"🔗 Connecting to MCP server: {server.name}...")
        await server.connect()
        print(f"✅ Connected to MCP server: {server.name}")

    trace_id = gen_trace_id()
    with trace(workflow_name="Manager-Developer Connector Build", trace_id=trace_id):
        trace_url = f"https://platform.openai.com/traces/trace?trace_id={trace_id}"

        run_prompt = (
            f"You are working on a connector build task for the API: '{api_name or 'N/A'}'. "
            "Your goal is to ensure the successful completion of all objectives as instructed."
        )

        update_progress_log("\n⚙️  Manager Agent is orchestrating the build...", session_state)
        update_progress_log(f"API Name: {api_name or 'N/A'}", session_state)
        update_progress_log(f"Additional Instructions: {instructions or 'N/A'}", session_state)
        update_progress_log(f"🔗 Follow along at: {trace_url}", session_state)
        open_if_browser_available(trace_url)

        try:
            # We loop until the manager calls the `mark_job_success` or `mark_job_failed` tool.
            # prev_response_id: str | None = None
            all_run_results = []
            iteration_count = 0
            while not is_complete(session_state):
                iteration_count += 1
                update_progress_log(
                    f"\n🔄 Starting iteration {iteration_count} with agent: {manager_agent.name}",
                    session_state,
                )
                run_result: RunResult = await Runner.run(
                    starting_agent=manager_agent,
                    input=run_prompt,
                    max_turns=MAX_CONNECTOR_BUILD_STEPS,
                    session=session,
                    # previous_response_id=prev_response_id,
                )
                all_run_results.append(run_result)  # Collect all run results
                # prev_response_id = run_result.raw_responses[-1].response_id if run_result.raw_responses else None
                status_msg = f"\n🤖 Iteration {iteration_count} completed. Last agent: {run_result.last_agent.name}"
                update_progress_log(status_msg, session_state)
                status_msg = f"🤖 {run_result.last_agent.name}: {run_result.final_output}"
                update_progress_log(status_msg, session_state)
                run_prompt = (
                    "You are still working on the connector build task. "
                    "Continue to the next step or raise an issue if needed. "
                    "The previous step output was:\n"
                    f"{run_result.final_output}"
                )

            # Return all run results
            return all_run_results

        except KeyboardInterrupt:
            update_progress_log("\n🛑 Build terminated (ctrl+c input received).", session_state)
            update_progress_log(f"🪵 Review trace logs at: {trace_url}", session_state)
            sys.exit(0)
        except Exception as ex:
            update_progress_log(f"\n❌ Unexpected error during build: {ex}", session_state)
            update_progress_log(f"🪵 Review trace logs at: {trace_url}", session_state)
            raise ex
