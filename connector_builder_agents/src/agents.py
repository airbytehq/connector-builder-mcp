# Copyright (c) 2025 Airbyte, Inc., all rights reserved.
"""Agent implementations for the Airbyte connector builder."""

from pydantic_ai import Agent, RunContext
from pydantic_ai.tools import duckduckgo_search

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
) -> Agent:
    """Create the developer agent that executes specific phases."""
    developer_agent = Agent(
        model,
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
            duckduckgo_search,
        ],
    )

    for mcp_server in mcp_servers:
        developer_agent.toolsets.append(mcp_server)

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
        model,
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
    )

    for mcp_server in mcp_servers:
        manager_agent.toolsets.append(mcp_server)

    @manager_agent.tool
    async def delegate_to_developer(
        ctx: RunContext[SessionState],
        assignment_title: str,
        assignment_description: str,
    ) -> str:
        """Delegate work to the developer agent.

        Args:
            assignment_title: Short title or key for this developer assignment.
            assignment_description: Detailed description of the task assigned to the developer,
                including all context and success criteria they need to complete it.
        """
        update_progress_log(
            f"🤝 [MANAGER → DEVELOPER] Manager delegating task to developer agent."
            f"\n Task Name: {assignment_title}"
            f"\n Task Description: {assignment_description}",
            ctx.deps,
        )

        result = await developer_agent.run(
            assignment_description,
            message_history=ctx.deps.message_history,
            deps=ctx.deps,
        )

        update_progress_log(
            f"🤝 [DEVELOPER → MANAGER] Developer completed task: {assignment_title}"
            f"\n Result: {result.data}",
            ctx.deps,
        )

        ctx.deps.message_history.extend(result.new_messages())

        return str(result.data)

    @developer_agent.tool
    async def report_back_to_manager(
        ctx: RunContext[SessionState],
        short_status: str,
        detailed_progress_update: str,
        is_full_success: bool = False,
        is_partial_success: bool = False,
        is_blocked: bool = False,
    ) -> str:
        """Report progress or issues back to the manager agent.

        Args:
            short_status: One sentence summary of what was accomplished.
            detailed_progress_update: A detailed update on progress and next steps.
            is_full_success: True if the phase is fully completed.
            is_partial_success: True if partially done.
            is_blocked: True if encountered a blocker.
        """
        update_progress_log(
            f"🤝 [DEVELOPER → MANAGER] Developer handing back control to manager."
            f"\n Summary of status: {short_status}"
            f"\n Partial success: {is_partial_success}"
            f"\n Full success: {is_full_success}"
            f"\n Blocked: {is_blocked}"
            f"\n Detailed progress update: {detailed_progress_update}",
            ctx.deps,
        )
        return "Status reported to manager"

    return manager_agent
