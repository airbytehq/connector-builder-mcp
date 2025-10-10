# Copyright (c) 2025 Airbyte, Inc., all rights reserved.
"""Tools and utilities for running MCP-based agents for connector building."""

from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Annotated

import emoji
from agents.mcp import (
    MCPServer,
    MCPServerStdio,
    MCPServerStdioParams,
)
from agents.mcp.util import create_static_tool_filter
from agents.tool import function_tool
from pydantic import BaseModel
from pydantic.fields import Field

# from agents import OpenAIConversationsSession
from .constants import HEADLESS_BROWSER


class SessionState(BaseModel):
    """Session state to track workspace and job status."""

    workspace_dir: Path
    execution_log_file: Path
    is_success: bool = False
    is_failed: bool = False
    start_time: datetime

    def __init__(self, workspace_dir: Path, **kwargs):
        execution_log_file = workspace_dir / "automated-execution-log.md"
        start_time = datetime.now()

        # Create the execution log file
        execution_log_file.write_text(
            f"# Automated Connector Build Log\n\n"
            "This file should not be edited directly. It is automatically updated by calls to the "
            "`log_progress_milestone` and `log_problem_encountered` tools.\n\n"
            f"⏳ Session started at {start_time.strftime('%Y-%m-%d %H:%M:%S')}\n\n",
            encoding="utf-8",
        )

        super().__init__(
            workspace_dir=workspace_dir,
            execution_log_file=execution_log_file,
            start_time=start_time,
            **kwargs,
        )

    def is_complete(self) -> bool:
        """Check if the job is marked as complete."""
        return self.is_success or self.is_failed


def create_session_state(workspace_dir: Path) -> SessionState:
    """Create a new session state with workspace directory."""
    return SessionState(workspace_dir=workspace_dir)


MCP_CONNECTOR_BUILDER_FOR_DEVELOPER = lambda: MCPServerStdio(  # noqa: E731
    # This should run from the local dev environment:
    name="airbyte-connector-builder-mcp-for-developer",
    params=MCPServerStdioParams(
        command="uv",
        args=[
            "run",
            "airbyte-connector-builder-mcp",
        ],
        env={},
    ),
    cache_tools_list=True,
    tool_filter=create_static_tool_filter(
        blocked_tool_names=[
            # Don't allow the agent to "cheat" by pulling an existing manifest directly (if exists).
            # TODO: Make this conditional based on the type of test we are doing:
            "get_connector_manifest",
            # When we aren't interactive, the agent needs to use the secrets that they have already:
            "populate_dotenv_missing_secrets_stubs",
        ],
    ),
    # TODO: Figure out how to make this timeout non-fatal to the LLM Agent:
    client_session_timeout_seconds=60 * 3,  # Longer timeout for long-running connector reads
)
MCP_CONNECTOR_BUILDER_FOR_MANAGER = lambda: MCPServerStdio(  # noqa: E731
    # This should run from the local dev environment:
    name="airbyte-connector-builder-mcp-for-manager",
    params=MCPServerStdioParams(
        command="uv",
        args=[
            "run",
            "airbyte-connector-builder-mcp",
        ],
        env={},
    ),
    cache_tools_list=True,
    tool_filter=create_static_tool_filter(
        allowed_tool_names=[
            "get_connector_builder_checklist",
            "run_connector_readiness_test_report",
            "list_dotenv_secrets",
        ],
    ),
    # TODO: Figure out how to make this timeout non-fatal to the LLM Agent:
    client_session_timeout_seconds=60 * 3,  # Longer timeout for long-running connector reads
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
    client_session_timeout_seconds=20,
)


def create_mcp_filesystem_server(session_state: SessionState) -> MCPServerStdio:
    """Create MCP filesystem server for the given session state."""
    return MCPServerStdio(
        name="agent-workspace-filesystem",
        params=MCPServerStdioParams(
            command="npx",
            args=[
                "mcp-server-filesystem",
                str(session_state.workspace_dir.absolute()),
            ],
            env={},
        ),
        cache_tools_list=True,
        client_session_timeout_seconds=10,
    )


def create_session_mcp_servers(
    session_state: SessionState,
) -> tuple[list[MCPServer], list[MCPServer], list[MCPServer]]:
    """Create all MCP servers for a session, reusing instances to avoid duplicates.

    Returns:
        Tuple of (all_servers, manager_servers, developer_servers)
    """
    # Create shared server instances
    connector_builder_dev = MCP_CONNECTOR_BUILDER_FOR_DEVELOPER()
    connector_builder_manager = MCP_CONNECTOR_BUILDER_FOR_MANAGER()
    filesystem_server = create_mcp_filesystem_server(session_state)

    # Create server lists reusing the same instances
    all_servers = [
        # MCP_PLAYWRIGHT_WEB_BROWSER(),
        connector_builder_dev,
        connector_builder_manager,
        filesystem_server,
    ]

    manager_servers = [
        connector_builder_manager,
        filesystem_server,
    ]

    developer_servers = [
        # MCP_PLAYWRIGHT_WEB_BROWSER(),
        connector_builder_dev,
        filesystem_server,
    ]

    return all_servers, manager_servers, developer_servers


def is_complete(session_state: SessionState) -> bool:
    """Check if the job is marked as complete."""
    return session_state.is_complete()


class AgentEnum(str, Enum):
    """Enum for agent names."""

    MANAGER_AGENT_NAME = "👨‍💼 Manager"
    DEVELOPER_AGENT_NAME = "👨‍💻 Developer"


def update_progress_log(
    message: str,
    session_state: SessionState,
    emoji_char: str | None = None,
) -> None:
    """Log a milestone message for tracking progress."""
    now = datetime.now()
    timestamp = now.strftime("%Y-%m-%d %H:%M:%S")
    elapsed = now - session_state.start_time
    elapsed_str = str(elapsed).split(".")[0]  # Remove microseconds for readability

    # Detect if the first character of message is an emoji:
    if message and emoji.is_emoji(message[0]):
        emoji_char, message = message[0], message[1:].lstrip()

    emoji_char = emoji_char or "📍"
    update_str = f"{emoji_char} Update [{timestamp}] ({elapsed_str} elapsed): {message}\n"

    with session_state.execution_log_file.open("a", encoding="utf-8") as f:
        f.write(update_str)

    print(update_str, flush=True)


def create_mark_job_success_tool(session_state: SessionState):
    """Create a mark_job_success tool bound to a specific session state."""

    @function_tool
    def mark_job_success() -> None:
        """Mark the current phase as complete.

        This should be called when all objectives for the current phase are met, and only after
        a successful connector readiness report has been saved to the workspace directory.
        """
        session_state.is_success = True
        update_progress_log("✅ Completed connector builder task successfully!", session_state)

    return mark_job_success


def create_mark_job_failed_tool(session_state: SessionState):
    """Create a mark_job_failed tool bound to a specific session state."""

    @function_tool
    def mark_job_failed() -> None:
        """Mark the current phase as failed.

        This should only be called in the event that it is no longer possible to make progress.
        Before calling this tool, you should attempt to save the latest output of the
        connector readiness report to the workspace directory for review.
        """
        session_state.is_failed = True
        update_progress_log("❌ Failed connector builder task.", session_state)

    return mark_job_failed


def log_progress_milestone(
    message: str,
    agent: AgentEnum,
    session_state: SessionState,
) -> None:
    """Log a milestone message for tracking progress."""
    update_progress_log(f"📍 {agent.value} Recorded a Milestone: {message}", session_state)


def log_problem_encountered(
    description: str,
    agent: AgentEnum,
    session_state: SessionState,
) -> None:
    """Log a problem encountered message."""
    update_progress_log(f"⚠️ {agent.value} Encountered a Problem: {description}", session_state)


def create_log_tool_failure_tool(session_state: SessionState):
    """Create a log_tool_failure tool bound to a specific session state."""

    @function_tool()
    def log_tool_failure(
        tool_name: Annotated[
            str,
            Field(description="Name of the tool that failed."),
        ],
        input_args: Annotated[str, Field(description="Input arguments for the tool.")],
        # *,
        summary_failure_description: Annotated[
            str, Field(description="Summary description of the failure.")
        ],
        is_unexpected_input_args_error: bool = False,
        is_unhelpful_error_message: bool = False,
        additional_info: str | None = None,
    ) -> None:
        """Log a tool failure message.

        This is a specialized version of `log_problem_encountered` to report tool failures.
        """
        msg = f"🛠️ Tool Failure in '{tool_name}': {summary_failure_description}"
        if is_unexpected_input_args_error:
            msg += " (🙈 Unexpected input arguments error)"
        if is_unhelpful_error_message:
            msg += " (🫤 Unhelpful error message)"
        msg += f"\n Input args: '{input_args}'"
        if additional_info:
            msg += f"\n Additional info: '{additional_info}'"

        update_progress_log(msg, session_state)

    return log_tool_failure


def create_log_problem_encountered_by_manager_tool(session_state: SessionState):
    """Create a log_problem_encountered tool for manager agent bound to a specific session state."""

    @function_tool(name_override="log_problem_encountered")
    def log_problem_encountered_by_manager(description: str) -> None:
        """Log a problem encountered message from the manager agent."""
        log_problem_encountered(description, AgentEnum.MANAGER_AGENT_NAME, session_state)

    return log_problem_encountered_by_manager


def create_log_problem_encountered_by_developer_tool(session_state: SessionState):
    """Create a log_problem_encountered tool for developer agent bound to a specific session state."""

    @function_tool(name_override="log_problem_encountered")
    def log_problem_encountered_by_developer(description: str) -> None:
        """Log a problem encountered message from the developer agent."""
        log_problem_encountered(description, AgentEnum.DEVELOPER_AGENT_NAME, session_state)

    return log_problem_encountered_by_developer


def create_log_progress_milestone_from_manager_tool(session_state: SessionState):
    """Create a log_progress_milestone tool for manager agent bound to a specific session state."""

    @function_tool(name_override="log_progress_milestone")
    def log_progress_milestone_from_manager(message: str) -> None:
        """Log a milestone message from the manager agent."""
        log_progress_milestone(message, AgentEnum.MANAGER_AGENT_NAME, session_state)

    return log_progress_milestone_from_manager


def create_log_progress_milestone_from_developer_tool(session_state: SessionState):
    """Create a log_progress_milestone tool for developer agent bound to a specific session state."""

    @function_tool(name_override="log_progress_milestone")
    def log_progress_milestone_from_developer(message: str) -> None:
        """Log a milestone message from the developer agent."""
        log_progress_milestone(message, AgentEnum.DEVELOPER_AGENT_NAME, session_state)

    return log_progress_milestone_from_developer


def create_get_progress_log_text_tool(session_state: SessionState):
    """Create a get_progress_log_text tool bound to a specific session state."""

    @function_tool
    def get_progress_log_text() -> str:
        """Get the current progress log text."""
        return session_state.execution_log_file.absolute().read_text(encoding="utf-8")

    return get_progress_log_text


def create_get_latest_readiness_report_tool(session_state: SessionState):
    """Create a get_latest_readiness_report tool bound to a specific session state."""

    @function_tool
    def get_latest_readiness_report() -> str:
        """Get the path to the latest connector readiness report, if it exists."""
        report_path = session_state.workspace_dir / "connector-readiness-report.md"
        if report_path.exists():
            return report_path.absolute().read_text(encoding="utf-8")

        return "No readiness report found."

    return get_latest_readiness_report
