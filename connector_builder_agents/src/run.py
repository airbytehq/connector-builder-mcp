# Copyright (c) 2025 Airbyte, Inc., all rights reserved.
"""Functions to run connector builder agents in different modalities."""

import sys
import time
from pathlib import Path

from pydantic_ai import Agent
from pydantic_ai.settings import ModelSettings

from ._util import get_secrets_dotenv
from .agents import (
    create_developer_agent,
    create_manager_agent,
)
from .constants import (
    DEFAULT_DEVELOPER_MODEL,
    DEFAULT_MANAGER_MODEL,
    ROOT_PROMPT_FILE_PATH,
)
from .tools import (
    SessionState,
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
) -> list | None:
    """Run an agentic AI connector build session with automatic mode selection."""
    if not api_name and not instructions:
        raise ValueError("Either api_name or instructions must be provided.")

    if api_name:
        instructions = (
            f"Fully build and test an Airbyte source connector for '{api_name}'. \n" + (instructions or "")
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
        prompt_file = ROOT_PROMPT_FILE_PATH
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
    workspace_dir = get_workspace_dir(session_id)
    session_state = create_session_state(workspace_dir)

    _, _, developer_servers = create_session_mcp_servers(session_state)
    agent = Agent(
        model,
        name="MCP Connector Builder",
        deps_type=SessionState,
        system_prompt=(
            "You are a helpful assistant with access to MCP tools for building Airbyte connectors."
        ),
        toolsets=developer_servers,
    )

    input_prompt: str = prompt
    while True:
        update_progress_log("\n⚙️  AI Agent is working...", session_state)
        try:
            result = await agent.run(
                input_prompt,
                message_history=session_state.message_history,
                deps=session_state,
            )

            session_state.message_history.extend(result.new_messages())

            update_progress_log(f"\n🤖  AI Agent: {result.output}", session_state)

            input_prompt = input("\n👤  You: ")
            if input_prompt.lower() in {"exit", "quit"}:
                update_progress_log("☑️ Ending conversation...", session_state)
                break

        except KeyboardInterrupt:
            update_progress_log(
                "\n🛑 Conversation terminated (ctrl+c input received).", session_state
            )
            sys.exit(0)

    return None


async def run_manager_developer_build(
    api_name: str | None = None,
    instructions: str | None = None,
    developer_model: str = DEFAULT_DEVELOPER_MODEL,
    manager_model: str = DEFAULT_MANAGER_MODEL,
    session_id: str | None = None,
) -> list:
    """Run a 3-phase connector build using manager-developer architecture."""
    if session_id is None:
        session_id = generate_session_id()

    workspace_dir = get_workspace_dir(session_id)
    session_state = create_session_state(workspace_dir)

    _, manager_servers, developer_servers = create_session_mcp_servers(session_state)

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

    run_prompt = (
        f"You are working on a connector build task for the API: '{api_name or 'N/A'}'. "
        "Your goal is to ensure the successful completion of all objectives as instructed."
    )

    update_progress_log("\n⚙️  Manager Agent is orchestrating the build...", session_state)
    update_progress_log(f"API Name: {api_name or 'N/A'}", session_state)
    update_progress_log(f"Additional Instructions: {instructions or 'N/A'}", session_state)

    try:
        all_run_results = []
        iteration_count = 0
        while not is_complete(session_state):
            iteration_count += 1
            update_progress_log(
                f"\n🔄 Starting iteration {iteration_count} with agent: {manager_agent.name}",
                session_state,
            )

            run_result = await manager_agent.run(
                run_prompt,
                message_history=session_state.message_history,
                deps=session_state,
            )

            all_run_results.append(run_result)

            session_state.message_history.extend(run_result.new_messages())

            status_msg = (
                f"\n🤖 Iteration {iteration_count} completed. Last agent: {manager_agent.name}"
            )
            update_progress_log(status_msg, session_state)
            status_msg = f"🤖 {manager_agent.name}: {run_result.output}"
            update_progress_log(status_msg, session_state)

            run_prompt = (
                "You are still working on the connector build task. "
                "Continue to the next step or raise an issue if needed. "
                "The previous step output was:\n"
                f"{run_result.output}"
            )

        return all_run_results

    except KeyboardInterrupt:
        update_progress_log("\n🛑 Build terminated (ctrl+c input received).", session_state)
        sys.exit(0)
    except Exception as ex:
        update_progress_log(f"\n❌ Unexpected error during build: {ex}", session_state)
        raise ex
