# Copyright (c) 2025 Airbyte, Inc., all rights reserved.
"""Agent implementations for the Airbyte connector builder."""

from agents import Agent as OpenAIAgent
from agents import (
    WebSearchTool,
    handoff,
)
from pydantic.main import BaseModel

# from agents import OpenAIConversationsSession
from .guidance import get_default_developer_prompt, get_default_manager_prompt
from .phases import Phase1Data, Phase2Data, Phase3Data
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

    async def on_phase1_handoff(ctx, input_data: Phase1Data) -> None:
        update_progress_log(
            f"🚀 Starting {input_data.phase_description} for {input_data.api_name}", session_state
        )

    async def on_phase2_handoff(ctx, input_data: Phase2Data) -> None:
        update_progress_log(
            f"🔄 Starting {input_data.phase_description} for {input_data.api_name}", session_state
        )

    async def on_phase3_handoff(ctx, input_data: Phase3Data) -> None:
        update_progress_log(
            f"🎯 Starting {input_data.phase_description} for {input_data.api_name}", session_state
        )

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


class ManagerHandoffInput(BaseModel):
    """Input data for handoff from developer back to manager."""

    short_status: str
    detailed_progress_update: str
    is_blocked: bool
    is_partial_success: bool
    is_full_success: bool


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
    developer_agent.handoffs.append(
        handoff(
            agent=manager_agent,
            tool_name_override="report_back_to_manager",
            tool_description_override="Report progress or issues back to the manager agent",
            input_type=ManagerHandoffInput,
            on_handoff=create_on_manager_handback(session_state),
        )
    )
