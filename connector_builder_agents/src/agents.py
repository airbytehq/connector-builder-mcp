# Copyright (c) 2025 Airbyte, Inc., all rights reserved.
"""Agent implementations for the Airbyte connector builder."""
from agents import Agent as OpenAIAgent
from agents import (
    handoff,
)
from pydantic.main import BaseModel

# from agents import OpenAIConversationsSession
from .constants import (
    WORKSPACE_WRITE_DIR,
)
from .guidance import get_default_developer_prompt, get_default_manager_prompt
from .phases import Phase1Data, Phase2Data, Phase3Data
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
        ],
    )


def create_manager_agent(
    developer_agent: OpenAIAgent,
    model: str,
    api_name: str,
    additional_instructions: str,
) -> OpenAIAgent:
    """Create the manager agent that orchestrates the 3-phase workflow."""

    async def on_phase1_handoff(ctx, input_data: Phase1Data) -> None:
        update_progress_log(f"🚀 Starting {input_data.phase_description} for {input_data.api_name}")

    async def on_phase2_handoff(ctx, input_data: Phase2Data) -> None:
        update_progress_log(f"🔄 Starting {input_data.phase_description} for {input_data.api_name}")

    async def on_phase3_handoff(ctx, input_data: Phase3Data) -> None:
        update_progress_log(f"🎯 Starting {input_data.phase_description} for {input_data.api_name}")

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


class ManagerHandoffInput(BaseModel):
    """Input data for handoff from developer back to manager."""

    short_status: str
    detailed_progress_update: str
    is_blocked: bool
    is_partial_success: bool
    is_full_success: bool


async def on_manager_handback(ctx, input_data: ManagerHandoffInput) -> None:
    update_progress_log(
        f"🤝 Handing back control to manager."
        "\n Summary of status: {input_data.short_status}"
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
    developer_agent.handoffs.append(
        handoff(
            agent=manager_agent,
            tool_name_override="report_back_to_manager",
            tool_description_override="Report progress or issues back to the manager agent",
            input_type=ManagerHandoffInput,
            on_handoff=on_manager_handback,
        )
    )
