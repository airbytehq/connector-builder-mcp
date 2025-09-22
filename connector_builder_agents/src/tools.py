# Copyright (c) 2025 Airbyte, Inc., all rights reserved.
"""Tools and utilities for running MCP-based agents for connector building."""

from datetime import datetime
from enum import Enum

from agents.mcp import (
    MCPServer,
    MCPServerStdio,
    MCPServerStdioParams,
)
from agents.mcp.util import create_static_tool_filter
from agents.tool import function_tool

# from agents import OpenAIConversationsSession
from .constants import HEADLESS_BROWSER, WORKSPACE_WRITE_DIR


# 🎯 Global flags to track job status:
IS_SUCCESS_FLAG: bool = False
IS_FAILED_FLAG: bool = False

START_TIME = datetime.now()

EXECUTION_LOG_FILE = WORKSPACE_WRITE_DIR / "automated-execution-log.md"
EXECUTION_LOG_FILE.write_text(
    f"# Automated Connector Build Log\n\n"
    "This file should not be edited directly. It is automatically updated by calls to the "
    "`log_progress_milestone` and `log_problem_encountered` tools.\n\n"
    f"⏳ Session started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n",
    encoding="utf-8",
)

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
    client_session_timeout_seconds=10,
)
ALL_MCP_SERVERS: list[MCPServer] = [
    # MCP_PLAYWRIGHT_WEB_BROWSER(),
    MCP_CONNECTOR_BUILDER_FOR_DEVELOPER(),
    MCP_FILESYSTEM_SERVER(),
]
MANAGER_AGENT_TOOLS: list[MCPServer] = [
    MCP_CONNECTOR_BUILDER_FOR_MANAGER(),
    MCP_FILESYSTEM_SERVER(),
]
DEVELOPER_AGENT_TOOLS: list[MCPServer] = [
    # MCP_PLAYWRIGHT_WEB_BROWSER(),
    MCP_CONNECTOR_BUILDER_FOR_DEVELOPER(),
    MCP_FILESYSTEM_SERVER(),
]


def is_complete() -> bool:
    """Check if the job is marked as complete."""
    return IS_SUCCESS_FLAG or IS_FAILED_FLAG


class AgentEnum(str, Enum):
    """Enum for agent names."""

    MANAGER_AGENT_NAME = "👨‍💼 Manager"
    DEVELOPER_AGENT_NAME = "👨‍💻 Developer"


def update_progress_log(
    message: str,
    emoji: str | None = None,
) -> None:
    """Log a milestone message for tracking progress."""
    now = datetime.now()
    timestamp = now.strftime("%Y-%m-%d %H:%M:%S")
    elapsed = now - START_TIME
    elapsed_str = str(elapsed).split(".")[0]  # Remove microseconds for readability

    # Detect if the first character of message is an emoji (unicode range):
    if message and ord(message[0]) in range(0x1F600, 0x1F64F):
        emoji: message = message[0], message[1:].lstrip()

    emoji = emoji or "📍"
    update_str = f"{emoji} Update [{timestamp}] ({elapsed_str} elapsed): {message}\n"
    with EXECUTION_LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(update_str)

    print(update_str, flush=True)


@function_tool
def mark_job_success() -> None:
    """Mark the current phase as complete.

    This should be called when all objectives for the current phase are met, and only after
    a successful connector readiness report has been saved to the workspace directory.
    """
    global IS_SUCCESS_FLAG
    IS_SUCCESS_FLAG = True
    update_progress_log("✅ Completed connector builder task successfully!")


@function_tool
def mark_job_failed() -> None:
    """Mark the current phase as failed.

    This should only be called in the event that it is no longer possible to make progress.
    Before calling this tool, you should attempt to save the latest output of the
    connector readiness report to the workspace directory for review.
    """
    global IS_FAILED_FLAG
    IS_FAILED_FLAG = True
    update_progress_log("❌ Failed connector builder task.")


def log_progress_milestone(
    message: str,
    agent: AgentEnum,
) -> None:
    """Log a milestone message for tracking progress."""
    update_progress_log(f"📍 {agent.value} Recorded a Milestone: {message}")


def log_problem_encountered(
    description: str,
    agent: AgentEnum,
) -> None:
    """Log a problem encountered message."""
    update_progress_log(f"⚠️ {agent.value} Encountered a Problem: {description}")


@function_tool(name_override="log_problem_encountered")
def log_problem_encountered_by_manager(description: str) -> None:
    """Log a problem encountered message from the manager agent."""
    log_problem_encountered(description, AgentEnum.MANAGER_AGENT_NAME)


@function_tool(name_override="log_problem_encountered")
def log_problem_encountered_by_developer(description: str) -> None:
    """Log a problem encountered message from the developer agent."""
    log_problem_encountered(description, AgentEnum.DEVELOPER_AGENT_NAME)


@function_tool(name_override="log_progress_milestone")
def log_progress_milestone_from_manager(message: str) -> None:
    """Log a milestone message from the manager agent."""
    log_progress_milestone(message, AgentEnum.MANAGER_AGENT_NAME)


@function_tool(name_override="log_progress_milestone")
def log_progress_milestone_from_developer(message: str) -> None:
    """Log a milestone message from the developer agent."""
    log_progress_milestone(message, AgentEnum.DEVELOPER_AGENT_NAME)
