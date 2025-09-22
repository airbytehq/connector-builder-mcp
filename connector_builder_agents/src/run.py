# Copyright (c) 2025 Airbyte, Inc., all rights reserved.
"""Functions to run connector builder agents in different modalities."""

import datetime
import sys
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
from ._util import open_if_browser_available
from .agents import (
    add_handback_to_manager,
    create_developer_agent,
    create_manager_agent,
)
from .constants import (
    DEFAULT_DEVELOPER_MODEL,
    DEFAULT_MANAGER_MODEL,
    MAX_CONNECTOR_BUILD_STEPS,
    SESSION_ID,
)
from .cost_tracking import CostTracker
from .tools import (
    ALL_MCP_SERVERS,
    DEVELOPER_AGENT_TOOLS,
    MANAGER_AGENT_TOOLS,
    is_complete,
    update_progress_log,
)


async def run_connector_build(
    api_name: str | None = None,
    instructions: str | None = None,
    developer_model: str = DEFAULT_DEVELOPER_MODEL,
    manager_model: str = DEFAULT_MANAGER_MODEL,
    *,
    interactive: bool = False,
) -> None:
    """Run an agentic AI connector build session with automatic mode selection."""
    if not api_name and not instructions:
        raise ValueError("Either api_name or instructions must be provided.")
    if api_name:
        instructions = (
            f"Fully build and test a connector for '{api_name}'. " + (instructions or "")
        ).strip()
    assert instructions, "By now, instructions should be non-null."

    if not interactive:
        print("\n🤖 Building Connector using Manager-Developer Architecture", flush=True)
        print("=" * 60, flush=True)
        print(f"API: {api_name or 'N/A'}")
        print(f"USER PROMPT: {instructions}", flush=True)
        print("=" * 60, flush=True)
        await run_manager_developer_build(
            api_name=api_name,
            instructions=instructions,
            developer_model=developer_model,
            manager_model=manager_model,
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
            model=developer_model,
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

        cost_tracker = CostTracker(trace_id=trace_id)
        cost_tracker.start_time = datetime.datetime.utcnow().isoformat()
        update_progress_log(f"🔢 Token usage tracking enabled for trace: {trace_id}")

        input_prompt: str = prompt
        while True:
            update_progress_log("\n⚙️  AI Agent is working...")
            update_progress_log(f"🔗 Follow along at: {trace_url}")
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
                        )
                        continue

                    if event.type == "raw_response_event":
                        continue

                    update_progress_log(f"[{event.type}] {str(event)[:120]}...")

                # After streaming ends, get the final result
                update_progress_log(f"\n🤖  AI Agent: {result_stream.final_output}")

                if hasattr(result_stream, "final_result") and result_stream.final_result:
                    cost_tracker.add_run_result(result_stream.final_result)
                    total_tokens = sum(
                        usage.total_tokens for usage in cost_tracker.model_usage.values()
                    )
                    update_progress_log(f"🔢 Session tokens: {total_tokens:,}")

                input_prompt = input("\n👤  You: ")
                if input_prompt.lower() in {"exit", "quit"}:
                    update_progress_log("☑️ Ending conversation...")
                    update_progress_log(f"🪵 Review trace logs at: {trace_url}")
                    break

            except KeyboardInterrupt:
                update_progress_log("\n🛑 Conversation terminated (ctrl+c input received).")
                update_progress_log(f"🪵 Review trace logs at: {trace_url}")
                sys.exit(0)
            finally:
                cost_tracker.end_time = datetime.datetime.utcnow().isoformat()
                cost_summary = cost_tracker.get_summary()

                if cost_summary["total_tokens"] > 0:
                    update_progress_log(
                        f"\n🔢 Session Total Tokens: {cost_summary['total_tokens']:,}"
                    )
                    update_progress_log(f"🔢 Total Requests: {cost_summary['total_requests']}")

                for server in ALL_MCP_SERVERS:
                    await server.cleanup()


async def run_manager_developer_build(
    api_name: str | None = None,
    instructions: str | None = None,
    developer_model: str = DEFAULT_DEVELOPER_MODEL,
    manager_model: str = DEFAULT_MANAGER_MODEL,
) -> None:
    """Run a 3-phase connector build using manager-developer architecture."""
    session = SQLiteSession(session_id=SESSION_ID)

    developer_agent = create_developer_agent(
        model=developer_model,
        api_name=api_name or "(see below)",
        additional_instructions=instructions or "",
    )
    manager_agent = create_manager_agent(
        developer_agent,
        model=manager_model,
        api_name=api_name or "(see below)",
        additional_instructions=instructions or "",
    )
    add_handback_to_manager(
        developer_agent=developer_agent,
        manager_agent=manager_agent,
    )

    for server in [*MANAGER_AGENT_TOOLS, *DEVELOPER_AGENT_TOOLS]:
        print(f"🔗 Connecting to MCP server: {server.name}...")
        await server.connect()
        print(f"✅ Connected to MCP server: {server.name}")

    trace_id = gen_trace_id()
    with trace(workflow_name="Manager-Developer Connector Build", trace_id=trace_id):
        trace_url = f"https://platform.openai.com/traces/trace?trace_id={trace_id}"

        cost_tracker = CostTracker(trace_id=trace_id)
        cost_tracker.start_time = datetime.datetime.utcnow().isoformat()

        run_prompt = (
            "You are working on a connector build task. "
            f"You are managing a connector build for the API: '{api_name or 'N/A'}'. "
            "Your goal is to ensure the successful completion of all phases as instructed."
        )

        update_progress_log("\n⚙️  Manager Agent is orchestrating the build...")
        update_progress_log(f"🔗 Follow along at: {trace_url}")
        update_progress_log(f"🔢 Token usage tracking enabled for trace: {trace_id}")
        open_if_browser_available(trace_url)

        try:
            # We loop until the manager calls the `mark_job_success` or `mark_job_failed` tool.
            # prev_response_id: str | None = None
            while not is_complete():
                run_result: RunResult = await Runner.run(
                    starting_agent=manager_agent,
                    input=run_prompt,
                    max_turns=MAX_CONNECTOR_BUILD_STEPS,
                    session=session,
                    # previous_response_id=prev_response_id,
                )

                cost_tracker.add_run_result(run_result)

                # prev_response_id = run_result.raw_responses[-1].response_id if run_result.raw_responses else None
                status_msg = f"\n🤖 {run_result.last_agent.name}: {run_result.final_output}"
                update_progress_log(status_msg)
                run_tokens = sum(
                    response.usage.total_tokens
                    for response in run_result.raw_responses
                    if response.usage
                )
                total_tokens = sum(
                    usage.total_tokens for usage in cost_tracker.model_usage.values()
                )
                update_progress_log(f"🔢 Run tokens: {run_tokens:,} | Total: {total_tokens:,}")

                run_prompt = (
                    "You are still working on the connector build task. "
                    "Continue to the next step or raise an issue if needed. "
                    "The previous step output was:\n"
                    f"{run_result.final_output}"
                )

        except KeyboardInterrupt:
            update_progress_log("\n🛑 Build terminated (ctrl+c input received).")
            update_progress_log(f"🪵 Review trace logs at: {trace_url}")
            sys.exit(0)
        except Exception as ex:
            update_progress_log(f"\n❌ Unexpected error during build: {ex}")
            update_progress_log(f"🪵 Review trace logs at: {trace_url}")
            sys.exit(1)
        finally:
            cost_tracker.end_time = datetime.datetime.utcnow().isoformat()

            update_progress_log(f"\n{cost_tracker.cost_summary_report}")

            try:
                from pathlib import Path
                from .constants import WORKSPACE_WRITE_DIR

                usage_dir = WORKSPACE_WRITE_DIR
                manifest_files = list(WORKSPACE_WRITE_DIR.glob("**/manifest.yaml"))
                if manifest_files:
                    usage_dir = manifest_files[0].parent
                    update_progress_log(f"📁 Found manifest at {manifest_files[0]}, saving usage data in same directory")
                else:
                    update_progress_log(f"📁 No manifest.yaml found, saving usage data in workspace directory")

                usage_file = usage_dir / f"{trace_id}_usage_summary.json"
                cost_tracker.save_to_file(usage_file)
                update_progress_log(f"📊 Detailed usage data saved to: {usage_file}")
            except Exception as save_ex:
                update_progress_log(f"⚠️  Could not save usage data: {save_ex}")

            for server in [*MANAGER_AGENT_TOOLS, *DEVELOPER_AGENT_TOOLS]:
                await server.cleanup()
