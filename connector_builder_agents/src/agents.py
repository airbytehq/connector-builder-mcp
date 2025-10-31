# Copyright (c) 2025 Airbyte, Inc., all rights reserved.
"""Agent implementations for the Airbyte connector builder."""

from pydantic import BaseModel, Field
from pydantic_ai import Agent, RunContext
from pydantic_ai.common_tools.duckduckgo import duckduckgo_search_tool
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.usage import UsageLimits

from .constants import PHASE_1_PROMPT_FILE_PATH, PHASE_2_PROMPT_FILE_PATH, PHASE_3_PROMPT_FILE_PATH
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


class DelegatedDeveloperTask(BaseModel):
    """Input data for handoff from manager to developer."""

    api_name: str = Field(description="The name of the API to build a connector for.")
    assignment_title: str = Field(description="The title of the task assigned to the developer.")
    assignment_description: str = Field(
        description="The description of the task assigned to the developer."
    )


class ManagerHandoffInput(BaseModel):
    """Input data for handoff from developer back to manager."""

    short_status: str = Field(description="A short status message for the build.")
    detailed_progress_update: str = Field(description="A detailed progress update for the build.")
    is_full_success: bool = Field(
        default=False, description="Whether the current task was successful."
    )
    is_partial_success: bool = Field(
        default=False, description="Whether the current task was partially successful."
    )
    is_blocked: bool = Field(default=False, description="Whether the current task is blocked.")


class ManagerTaskOutput(BaseModel):
    """Output data for a manager iteration."""

    short_status: str = Field(description="A short status message for the build.")
    detailed_progress_update: str = Field(description="A detailed progress update for the build.")
    phase_1_completed: bool = Field(default=False, description="Whether phase 1 was completed.")
    phase_2_completed: bool = Field(default=False, description="Whether phase 2 was completed.")
    phase_3_completed: bool = Field(default=False, description="Whether phase 3 was completed.")
    is_blocked: bool = Field(default=False, description="Whether the build is blocked.")


def create_developer_agent(
    model: str,
    api_name: str,
    additional_instructions: str,
    session_state: SessionState,
    mcp_servers: list,
) -> Agent:
    """Create the developer agent that executes specific phases."""
    developer_agent = Agent(
        OpenAIChatModel(model_name=model),
        name="MCP Connector Developer",
        deps_type=SessionState,
        system_prompt=get_default_developer_prompt(
            api_name=api_name,
            instructions=additional_instructions,
            project_directory=session_state.workspace_dir.absolute(),
        ),
        tools=[
            create_log_progress_milestone_from_developer_tool(session_state),
            create_log_problem_encountered_by_developer_tool(session_state),
            create_log_tool_failure_tool(session_state),
            duckduckgo_search_tool(),
        ],
        toolsets=mcp_servers,
        output_type=ManagerHandoffInput,
        instrument=True,
    )

    return developer_agent


def create_manager_agent(
    developer_agent: Agent,
    model: str,
    api_name: str,
    additional_instructions: str,
    session_state: SessionState,
    mcp_servers: list,
) -> Agent:
    """Create the manager agent that orchestrates the 3-phase workflow."""
    manager_agent = Agent(
        OpenAIChatModel(model_name=model),
        name="Connector Builder Manager",
        deps_type=SessionState,
        system_prompt=get_default_manager_prompt(
            api_name=api_name,
            instructions=additional_instructions,
            project_directory=session_state.workspace_dir.absolute(),
        ),
        tools=[
            create_mark_job_success_tool(session_state),
            create_mark_job_failed_tool(session_state),
            create_log_problem_encountered_by_manager_tool(session_state),
            create_log_progress_milestone_from_manager_tool(session_state),
            create_log_tool_failure_tool(session_state),
            create_get_latest_readiness_report_tool(session_state),
            create_get_progress_log_text_tool(session_state),
        ],
        toolsets=mcp_servers,
        output_type=ManagerTaskOutput,
        instrument=True,
    )

    @manager_agent.tool
    async def delegate_to_developer(
        ctx: RunContext[SessionState],
        delegated_developer_task: DelegatedDeveloperTask,
    ) -> DelegatedDeveloperTask:
        """Delegate work to the developer agent.

        Args:
            assignment_title: Short title or key for this developer assignment.
            assignment_description: Detailed description of the task assigned to the developer,
                including all context and success criteria they need to complete it.
        """
        update_progress_log(
            f"🤝 [MANAGER → DEVELOPER] Manager delegating task to developer agent."
            f"\n Task Name: {delegated_developer_task.assignment_title}"
            f"\n Task Description: {delegated_developer_task.assignment_description}",
            ctx.deps,
        )

        result = await developer_agent.run(
            delegated_developer_task.assignment_description,
            message_history=ctx.deps.message_history,
            deps=ctx.deps,
            usage_limits=UsageLimits(request_limit=100),
        )

        update_progress_log(
            f"🤝 [DEVELOPER → MANAGER] Developer completed task: {delegated_developer_task.assignment_title}"
            f"\n Result: {result.output}",
            ctx.deps,
        )

        ctx.deps.message_history.extend(result.new_messages())

        return result.output

    @manager_agent.tool
    async def start_phase_1(
        ctx: RunContext[SessionState],
    ) -> str:
        """Start phase 1 of the connector build. Returns the prompt for phase 1."""
        update_progress_log("🔧 [Manager] MCP Tool call: start_phase_1", ctx.deps)
        return PHASE_1_PROMPT_FILE_PATH.read_text(encoding="utf-8")

    @manager_agent.tool
    async def start_phase_2(
        ctx: RunContext[SessionState],
    ) -> str:
        """Start phase 2 of the connector build. Returns the prompt for phase 2."""
        update_progress_log("🔧 [Manager] MCP Tool call: start_phase_2", ctx.deps)
        return PHASE_2_PROMPT_FILE_PATH.read_text(encoding="utf-8")

    @manager_agent.tool
    async def start_phase_3(
        ctx: RunContext[SessionState],
    ) -> str:
        """Start phase 3 of the connector build. Returns the prompt for phase 3."""
        update_progress_log("🔧 [Manager] MCP Tool call: start_phase_3", ctx.deps)
        return PHASE_3_PROMPT_FILE_PATH.read_text(encoding="utf-8")

    return manager_agent
