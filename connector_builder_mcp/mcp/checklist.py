"""MCP tools for checklist management.

This module provides the MCP integration layer for the checklist system.
Domain models and persistence logic are in _checklist_utils.py.
"""

import logging
from typing import Annotated

from fastmcp import Context, FastMCP
from pydantic import Field

from connector_builder_mcp._checklist_utils import (
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
def list_tasks(ctx: Context) -> dict:
    """List all tasks in the checklist grouped by type.

    Returns:
        Dictionary containing:
        - connector_tasks: List of general connector tasks
        - stream_tasks: Dict of stream tasks, keyed by stream name
        - special_requirements: List of special requirement tasks
        - acceptance_tests: List of acceptance test tasks
        - finalization_tasks: List of finalization tasks
        - summary: Task status summary (total, not_started, in_progress, completed, blocked)
    """
    logger.info("Listing all tasks in checklist")
    checklist = load_session_checklist(ctx.session_id)
    return {
        "connector_tasks": [task.model_dump() for task in checklist.basic_connector_tasks],
        "stream_tasks": {
            stream_name: [task.model_dump() for task in tasks]
            for stream_name, tasks in checklist.stream_tasks.items()
        },
        "special_requirements": [task.model_dump() for task in checklist.special_requirements],
        "acceptance_tests": [task.model_dump() for task in checklist.acceptance_tests],
        "finalization_tasks": [task.model_dump() for task in checklist.finalization_tasks],
        "summary": checklist.get_summary(),
    }


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


@mcp_tool(
    domain=ToolDomain.CHECKLIST,
)
def reset_checklist(ctx: Context) -> dict:
    """Reset the checklist to the default connector build task list.

    This will clear all tasks and restore the default set of connector build tasks.

    Returns:
        Success message with the new task list summary
    """
    logger.info("Resetting checklist to default")
    checklist = TaskList.new_connector_build_task_list()
    save_session_checklist(ctx.session_id, checklist)
    return {
        "success": True,
        "message": "Checklist reset to default connector build tasks",
        "summary": checklist.get_summary(),
    }


@mcp_tool(
    domain=ToolDomain.CHECKLIST,
)
def add_special_requirements(
    ctx: Context,
    requirements: Annotated[
        list[str],
        Field(description="List of special requirement descriptions to add as tasks"),
    ],
) -> dict:
    """Add special requirement tasks to the checklist.

    This is the only way for agents to add custom tasks to the checklist.
    Each requirement will be converted to a task with a generated ID.

    Returns:
        Dictionary with added tasks and updated summary
    """
    logger.info(f"Adding {len(requirements)} special requirements")
    checklist = load_session_checklist(ctx.session_id)
    added_tasks = add_special_requirements_to_checklist(checklist, requirements)
    save_session_checklist(ctx.session_id, checklist)
    return {
        "success": True,
        "added_tasks": added_tasks,
        "summary": checklist.get_summary(),
    }


def register_checklist_tools(
    app: FastMCP,
):
    """Register checklist tools in the MCP server."""
    register_mcp_tools(app, domain=ToolDomain.CHECKLIST)
