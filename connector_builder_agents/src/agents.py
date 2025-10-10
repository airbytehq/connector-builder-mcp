# Copyright (c) 2025 Airbyte, Inc., all rights reserved.
"""Agent implementations for the Airbyte connector builder."""

from collections.abc import Callable

from agents import Agent as OpenAIAgent
from agents import (
    WebSearchTool,
    handoff,
)
from pydantic.main import BaseModel

# from agents import OpenAIConversationsSession
from .guidance import get_default_developer_prompt, get_default_manager_prompt
from .tools import (
    SessionState,
    create_get_latest_readiness_report_tool,
    create_get_progress_log_text_tool,
    create_log_problem_encountered_by_developer_tool,
    create_log_problem_encountered_by_manager_tool,
    create_log_progress_milestone_from_developer_tool,
    create_log_progress_milestone_from_manager_tool,
    create_log_tool_failure_tool,
    create_mark_job_failed_tool,
    create_mark_job_success_tool,
    update_progress_log,
)


def create_developer_agent(
    model: str,
    api_name: str,
    additional_instructions: str,
    session_state: SessionState,
    mcp_servers: list,
) -> OpenAIAgent:
    """Create the developer agent that executes specific phases."""
    return OpenAIAgent(
        name="MCP Connector Developer",
        instructions=get_default_developer_prompt(
            api_name=api_name,
            instructions=additional_instructions,
            project_directory=session_state.workspace_dir.absolute(),
        ),
        mcp_servers=mcp_servers,
        model=model,
        tools=[
            create_log_progress_milestone_from_developer_tool(session_state),
            create_log_problem_encountered_by_developer_tool(session_state),
            create_log_tool_failure_tool(session_state),
            WebSearchTool(),
        ],
    )


def create_manager_agent(
    developer_agent: OpenAIAgent,
    model: str,
    api_name: str,
    additional_instructions: str,
    session_state: SessionState,
    mcp_servers: list,
) -> OpenAIAgent:
    """Create the manager agent that orchestrates the 3-phase workflow."""
    return OpenAIAgent(
        name="Connector Builder Manager",
        instructions=get_default_manager_prompt(
            api_name=api_name,
            instructions=additional_instructions,
            project_directory=session_state.workspace_dir.absolute(),
        ),
        handoffs=[
            handoff(
                agent=developer_agent,
                tool_name_override="delegate_to_developer",
                tool_description_override="Delegating work to the developer agent",
                input_type=DelegatedDeveloperTask,
                on_handoff=create_on_developer_delegation(session_state),
            ),
        ],
        mcp_servers=mcp_servers,
        model=model,
        tools=[
            create_mark_job_success_tool(session_state),
            create_mark_job_failed_tool(session_state),
            create_log_problem_encountered_by_manager_tool(session_state),
            create_log_progress_milestone_from_manager_tool(session_state),
            create_log_tool_failure_tool(session_state),
            create_get_latest_readiness_report_tool(session_state),
            create_get_progress_log_text_tool(session_state),
        ],
    )


class DelegatedDeveloperTask(BaseModel):
    """Input data for handoff from manager to developer."""

    api_name: str
    assignment_title: str
    assignment_description: str


class ManagerHandoffInput(BaseModel):
    """Input data for handoff from developer back to manager."""

    short_status: str
    detailed_progress_update: str
    is_full_success: bool
    is_partial_success: bool
    is_blocked: bool


def create_on_developer_delegation(session_state: SessionState) -> Callable:
    """Create an on_developer_delegation callback bound to a specific session state."""

    async def on_developer_delegation(ctx, input_data: DelegatedDeveloperTask) -> None:
        update_progress_log(
            f"🤝 Delegating task to developer agent."
            f"\n Task Name: {input_data.assignment_title}"
            f"\n Task Description: {input_data.assignment_description}",
            session_state,
        )

    return on_developer_delegation


def create_on_manager_handback(session_state: SessionState):
    """Create an on_manager_handback callback bound to a specific session state."""

    async def on_manager_handback(ctx, input_data: ManagerHandoffInput) -> None:
        update_progress_log(
            f"🤝 Handing back control to manager."
            f"\n Summary of status: {input_data.short_status}"
            f"\n Partial success: {input_data.is_partial_success}"
            f"\n Full success: {input_data.is_full_success}"
            f"\n Blocked: {input_data.is_blocked}"
            f"\n Detailed progress update: {input_data.detailed_progress_update}",
            session_state,
        )

    return on_manager_handback


def add_handback_to_manager(
    developer_agent: OpenAIAgent,
    manager_agent: OpenAIAgent,
    session_state: SessionState,
) -> None:
    """Add a handoff from the developer back to the manager to report progress."""
    developer_agent.handoffs.extend(
        [
            handoff(
                agent=manager_agent,
                tool_name_override="report_back_to_manager",
                tool_description_override="Report progress or issues back to the manager agent",
                input_type=ManagerHandoffInput,
                on_handoff=create_on_manager_handback(session_state),
            ),
            handoff(
                agent=manager_agent,
                tool_name_override="report_task_completion_to_manager",
                tool_description_override="Report task completion to the manager agent",
                input_type=ManagerHandoffInput,
                on_handoff=create_on_manager_handback(session_state),
            ),
        ]
    )
