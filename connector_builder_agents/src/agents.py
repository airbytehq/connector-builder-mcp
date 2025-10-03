# Copyright (c) 2025 Airbyte, Inc., all rights reserved.
"""Agent implementations for the Airbyte connector builder."""

from agents import Agent as OpenAIAgent
from agents import (
    WebSearchTool,
    handoff,
)
from pydantic.main import BaseModel

# from agents import OpenAIConversationsSession
from .constants import (
    WORKSPACE_WRITE_DIR,
)
from .guidance import get_default_developer_prompt, get_default_manager_prompt
from .tools import (
    DEVELOPER_AGENT_TOOLS,
    MANAGER_AGENT_TOOLS,
    get_latest_readiness_report,
    get_progress_log_text,
    log_problem_encountered_by_developer,
    log_problem_encountered_by_manager,
    log_progress_milestone_from_developer,
    log_progress_milestone_from_manager,
    log_tool_failure,
    mark_job_failed,
    mark_job_success,
    update_progress_log,
)


def create_developer_agent(
    model: str,
    api_name: str,
    additional_instructions: str,
) -> OpenAIAgent:
    """Create the developer agent that executes specific phases."""
    return OpenAIAgent(
        name="MCP Connector Developer",
        instructions=get_default_developer_prompt(
            api_name=api_name,
            instructions=additional_instructions,
            project_directory=WORKSPACE_WRITE_DIR.absolute(),
        ),
        mcp_servers=DEVELOPER_AGENT_TOOLS,
        model=model,
        tools=[
            log_progress_milestone_from_developer,
            log_problem_encountered_by_developer,
            log_tool_failure,
            WebSearchTool(),
        ],
    )


def create_manager_agent(
    developer_agent: OpenAIAgent,
    model: str,
    api_name: str,
    additional_instructions: str,
) -> OpenAIAgent:
    """Create the manager agent that orchestrates the 3-phase workflow."""
    return OpenAIAgent(
        name="Connector Builder Manager",
        instructions=get_default_manager_prompt(
            api_name=api_name,
            instructions=additional_instructions,
            project_directory=WORKSPACE_WRITE_DIR.absolute(),
        ),
        handoffs=[
            handoff(
                agent=developer_agent,
                tool_name_override="delegate_to_developer",
                tool_description_override="Delegating work to the developer agent",
                input_type=DelegatedDeveloperTask,
                on_handoff=on_developer_delegation,
            ),
        ],
        mcp_servers=MANAGER_AGENT_TOOLS,
        model=model,
        tools=[
            mark_job_success,
            mark_job_failed,
            log_problem_encountered_by_manager,
            log_progress_milestone_from_manager,
            log_tool_failure,
            get_latest_readiness_report,
            get_progress_log_text,
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


async def on_developer_delegation(ctx, input_data: DelegatedDeveloperTask) -> None:
    update_progress_log(
        f"🤝 Delegating task to developer agent."
        f"\n Task Name: {input_data.assignment_title}"
        f"\n Task Description: {input_data.assignment_description}"
    )


async def on_manager_handback(ctx, input_data: ManagerHandoffInput) -> None:
    update_progress_log(
        f"🤝 Handing back control to manager."
        f"\n Summary of status: {input_data.short_status}"
        f"\n Partial success: {input_data.is_partial_success}"
        f"\n Full success: {input_data.is_full_success}"
        f"\n Blocked: {input_data.is_blocked}"
        f"\n Detailed progress update: {input_data.detailed_progress_update}"
    )


def add_handback_to_manager(
    developer_agent: OpenAIAgent,
    manager_agent: OpenAIAgent,
) -> None:
    """Add a handoff from the developer back to the manager to report progress."""
    developer_agent.handoffs.extend([
        handoff(
            agent=manager_agent,
            tool_name_override="report_back_to_manager",
            tool_description_override="Report progress or issues back to the manager agent",
            input_type=ManagerHandoffInput,
            on_handoff=on_manager_handback,
        ),
        handoff(
            agent=manager_agent,
            tool_name_override="report_task_completion_to_manager",
            tool_description_override="Report task completion to the manager agent",
            input_type=ManagerHandoffInput,
            on_handoff=on_manager_handback,
        ),
    ])
