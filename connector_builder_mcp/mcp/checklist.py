"""MCP tools for checklist management.

This module provides the MCP integration layer for the checklist system.
Domain models and persistence logic are in _checklist_utils.py.
"""

import logging
from typing import Annotated

from fastmcp import Context, FastMCP
from pydantic import Field
from pydantic.main import BaseModel

from connector_builder_mcp._checklist_utils import (
    Task,
    TaskList,
    TaskStatusEnum,
    add_special_requirements_to_checklist,
    load_session_checklist,
    save_session_checklist,
)
from connector_builder_mcp.mcp._mcp_utils import ToolDomain, mcp_tool, register_mcp_tools


logger = logging.getLogger(__name__)


@mcp_tool(
    domain=ToolDomain.CHECKLIST,
    read_only=True,
    idempotent=True,
)
def get_connector_builder_checklist(ctx: Context) -> TaskList:
    """List all tasks in the checklist grouped by type.

    Call update_task_status to modify task statuses.
    """
    logger.info("Listing all tasks in checklist")
    return load_session_checklist(ctx.session_id)


@mcp_tool(
    domain=ToolDomain.CHECKLIST,
)
def update_task_status(
    ctx: Context,
    task_id: Annotated[str, Field(description="Unique identifier for the task")],
    status: Annotated[
        TaskStatusEnum,
        Field(description="New status for the task"),
    ],
    status_detail: Annotated[
        str | None,
        Field(
            description="Optional details about the status change (e.g., what was accomplished, what is blocking)"
        ),
    ] = None,
) -> dict:
    """Update the status of a task.

    Returns:
        The updated task as a dictionary

    Raises:
        ValueError: If task_id is not found
    """
    logger.info(f"Updating task status for {task_id} to {status}")
    checklist = load_session_checklist(ctx.session_id)

    task = checklist.get_task_by_id(task_id)
    if not task:
        raise ValueError(f"Task with ID '{task_id}' not found.")

    task.status = status
    task.status_detail = status_detail

    save_session_checklist(ctx.session_id, checklist)
    return task.model_dump()


class NextTasksResult(BaseModel):
    next_tasks: list[Task]
    blocked: list[Task]


@mcp_tool(
    domain=ToolDomain.CHECKLIST,
    read_only=True,
)
def get_next_tasks(
    ctx: Context,
    count: int = 1,
) -> NextTasksResult:
    """Get the next N tasks that are not yet completed.

    Returns both the next tasks to work on (prioritizing in-progress before not-started)
    and any blocked tasks that need attention.
    """
    logger.info(f"Getting next {count} tasks")
    checklist = load_session_checklist(ctx.session_id)
    return NextTasksResult(
        next_tasks=checklist.get_next_tasks(count),
        blocked=checklist.get_blocked_tasks(),
    )


# @mcp_tool(
#     domain=ToolDomain.CHECKLIST,
# )
# def reset_checklist(ctx: Context) -> dict:
#     """Reset the checklist to the default connector build task list.

#     This will clear all tasks and restore the default set of connector build tasks.

#     Returns:
#         Success message with the new task list summary
#     """
#     logger.info("Resetting checklist to default")
#     checklist = TaskList.new_connector_build_task_list()
#     save_session_checklist(ctx.session_id, checklist)
#     return {
#         "success": True,
#         "message": "Checklist reset to default connector build tasks",
#         "summary": checklist.get_summary(),
#     }


@mcp_tool(
    domain=ToolDomain.CHECKLIST,
)
def add_special_requirements(
    ctx: Context,
    requirements: Annotated[
        list[str],
        Field(description="List of special requirement descriptions to add as tasks"),
    ],
) -> str:
    """Add special requirement tasks to the checklist.

    This is the only way for agents to add custom tasks to the checklist.
    Each requirement will be converted to a task with a generated ID.

    Returns:
        Dictionary with added tasks and updated summary
    """
    logger.info(f"Adding {len(requirements)} special requirements")
    checklist = load_session_checklist(ctx.session_id)
    add_special_requirements_to_checklist(checklist, requirements)
    save_session_checklist(ctx.session_id, checklist)
    return "Success! Task(s) added to checklist."


def register_checklist_tools(
    app: FastMCP,
):
    """Register checklist tools in the MCP server."""
    register_mcp_tools(app, domain=ToolDomain.CHECKLIST)
