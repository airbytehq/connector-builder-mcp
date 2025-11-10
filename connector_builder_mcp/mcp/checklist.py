"""Checklist tools for tracking connector development progress.

This module provides MCP tools for managing a task checklist during connector development.
The checklist tracks three types of tasks:
- Connector Tasks: General connector setup and configuration
- Stream Tasks: Stream-specific implementation work
- Finalization Tasks: Final validation and cleanup
"""

import logging
from enum import Enum
from typing import Annotated

from fastmcp import FastMCP
from pydantic import BaseModel, Field

from connector_builder_mcp.mcp._mcp_utils import ToolDomain, mcp_tool, register_mcp_tools


logger = logging.getLogger(__name__)


class TaskStatusEnum(str, Enum):
    """Status of a task in the task list."""

    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    BLOCKED = "blocked"


class TaskTypeEnum(str, Enum):
    """Types of tasks in the task list."""

    CONNECTOR = "connector"
    STREAM = "stream"
    FINALIZATION = "finalization"


class Task(BaseModel):
    """Base task model with common fields."""

    task_type: TaskTypeEnum = Field(description="Type of task (connector, stream, or finalization)")
    id: str = Field(description="Unique identifier for the task")
    task_name: str = Field(description="Short name/title of the task")
    description: str | None = Field(
        default=None,
        description="Optional longer description with additional context/instructions",
    )
    status: TaskStatusEnum = TaskStatusEnum.NOT_STARTED
    status_detail: str | None = Field(
        default=None,
        description="Details about the task status. Can be set when marking task as completed, blocked, or in progress to provide context.",
    )


class ConnectorTask(Task):
    """General connector task for pre-stream work."""

    task_type: TaskTypeEnum = TaskTypeEnum.CONNECTOR


class StreamTask(Task):
    """Stream-specific task with an additional stream name field."""

    task_type: TaskTypeEnum = TaskTypeEnum.STREAM
    stream_name: str = Field(description="Name of the stream this task relates to")


class FinalizationTask(Task):
    """Finalization task for post-stream work."""

    task_type: TaskTypeEnum = TaskTypeEnum.FINALIZATION


class TaskList(BaseModel):
    """Generic task list for tracking progress."""

    basic_connector_tasks: list[ConnectorTask] = Field(
        default_factory=list,
        description="List of basic connector tasks",
    )
    stream_tasks: list[StreamTask] = Field(
        default_factory=list,
        description="List of stream tasks",
    )
    finalization_tasks: list[FinalizationTask] = Field(
        default_factory=list,
        description="List of finalization tasks",
    )

    @property
    def tasks(self) -> list[Task]:
        """Get all tasks combined from all task lists."""
        result: list[Task] = []
        result.extend(self.basic_connector_tasks)
        result.extend(self.stream_tasks)
        result.extend(self.finalization_tasks)
        return result

    def get_task_by_id(self, task_id: str) -> Task | None:
        """Get a task by its ID."""
        for task in self.tasks:
            if task.id == task_id:
                return task
        return None

    def get_summary(self) -> dict[str, int]:
        """Get a summary of task statuses."""
        total = len(self.tasks)
        not_started = sum(1 for t in self.tasks if t.status == TaskStatusEnum.NOT_STARTED)
        in_progress = sum(1 for t in self.tasks if t.status == TaskStatusEnum.IN_PROGRESS)
        completed = sum(1 for t in self.tasks if t.status == TaskStatusEnum.COMPLETED)
        blocked = sum(1 for t in self.tasks if t.status == TaskStatusEnum.BLOCKED)

        return {
            "total": total,
            "not_started": not_started,
            "in_progress": in_progress,
            "completed": completed,
            "blocked": blocked,
        }

    @classmethod
    def new_connector_build_task_list(cls) -> "TaskList":
        """Create a new task list with default connector build tasks."""
        return cls(
            basic_connector_tasks=[
                ConnectorTask(
                    id="collect-info",
                    task_name="Collect information from user",
                    description="Gather requirements, API details, authentication info, and user expectations",
                ),
                ConnectorTask(
                    id="research-api",
                    task_name="Research and analyze source API",
                    description="Study API documentation, endpoints, rate limits, and data structures",
                ),
                ConnectorTask(
                    id="first-stream-tasks",
                    task_name="Enumerate streams and create first stream's tasks",
                    description="Identify all available streams and create detailed tasks for implementing the first stream",
                ),
            ],
            stream_tasks=[],
            finalization_tasks=[
                FinalizationTask(
                    id="readiness-pass-1",
                    task_name="Run connector readiness report",
                    description="Execute readiness check. If issues exist, go back and fix them. Otherwise, create tasks for remaining streams that were enumerated",
                ),
                FinalizationTask(
                    id="readiness-pass-2",
                    task_name="Run connector readiness report",
                    description="Execute final readiness check and create new tasks based on findings",
                ),
            ],
        )


_checklist = TaskList.new_connector_build_task_list()


@mcp_tool(
    domain=ToolDomain.GUIDANCE,
)
def list_tasks() -> dict:
    """List all tasks in the checklist grouped by type.

    Returns:
        Dictionary containing:
        - connector_tasks: List of general connector tasks
        - stream_tasks: List of stream-specific tasks
        - finalization_tasks: List of finalization tasks
        - summary: Task status summary (total, not_started, in_progress, completed, blocked)
    """
    logger.info("Listing all tasks in checklist")
    return {
        "connector_tasks": [task.model_dump() for task in _checklist.basic_connector_tasks],
        "stream_tasks": [task.model_dump() for task in _checklist.stream_tasks],
        "finalization_tasks": [task.model_dump() for task in _checklist.finalization_tasks],
        "summary": _checklist.get_summary(),
    }


@mcp_tool(
    domain=ToolDomain.GUIDANCE,
)
def add_connector_task(
    task_id: Annotated[str, Field(description="Unique identifier for the task")],
    task_name: Annotated[str, Field(description="Short name/title of the task")],
    description: Annotated[
        str | None,
        Field(description="Optional longer description with additional context/instructions"),
    ] = None,
) -> dict:
    """Add a new connector task to the end of the connector tasks list.

    Args:
        task_id: Unique identifier for the task
        task_name: Short name/title of the task
        description: Optional longer description

    Returns:
        The created task as a dictionary
    """
    logger.info(f"Adding connector task: {task_id}")
    task = ConnectorTask(
        id=task_id,
        task_name=task_name,
        description=description,
    )
    _checklist.basic_connector_tasks.append(task)
    return task.model_dump()


@mcp_tool(
    domain=ToolDomain.GUIDANCE,
)
def insert_connector_task(
    position: Annotated[int, Field(description="Position to insert the task (0-indexed)")],
    task_id: Annotated[str, Field(description="Unique identifier for the task")],
    task_name: Annotated[str, Field(description="Short name/title of the task")],
    description: Annotated[
        str | None,
        Field(description="Optional longer description with additional context/instructions"),
    ] = None,
) -> dict:
    """Insert a new connector task at a specific position.

    Args:
        position: Position to insert the task (0-indexed)
        task_id: Unique identifier for the task
        task_name: Short name/title of the task
        description: Optional longer description

    Returns:
        The created task as a dictionary
    """
    logger.info(f"Inserting connector task at position {position}: {task_id}")
    task = ConnectorTask(
        id=task_id,
        task_name=task_name,
        description=description,
    )
    position = max(0, min(position, len(_checklist.basic_connector_tasks)))
    _checklist.basic_connector_tasks.insert(position, task)
    return task.model_dump()


@mcp_tool(
    domain=ToolDomain.GUIDANCE,
)
def add_stream_task(
    stream_name: Annotated[str, Field(description="Name of the stream this task relates to")],
    task_id: Annotated[str, Field(description="Unique identifier for the task")],
    task_name: Annotated[str, Field(description="Short name/title of the task")],
    description: Annotated[
        str | None,
        Field(description="Optional longer description with additional context/instructions"),
    ] = None,
) -> dict:
    """Add a new stream task to the end of the stream tasks list.

    Args:
        stream_name: Name of the stream this task relates to
        task_id: Unique identifier for the task
        task_name: Short name/title of the task
        description: Optional longer description

    Returns:
        The created task as a dictionary
    """
    logger.info(f"Adding stream task for {stream_name}: {task_id}")
    task = StreamTask(
        id=task_id,
        stream_name=stream_name,
        task_name=task_name,
        description=description,
    )
    _checklist.stream_tasks.append(task)
    return task.model_dump()


@mcp_tool(
    domain=ToolDomain.GUIDANCE,
)
def insert_stream_task(
    position: Annotated[int, Field(description="Position to insert the task (0-indexed)")],
    stream_name: Annotated[str, Field(description="Name of the stream this task relates to")],
    task_id: Annotated[str, Field(description="Unique identifier for the task")],
    task_name: Annotated[str, Field(description="Short name/title of the task")],
    description: Annotated[
        str | None,
        Field(description="Optional longer description with additional context/instructions"),
    ] = None,
) -> dict:
    """Insert a new stream task at a specific position.

    Args:
        position: Position to insert the task (0-indexed)
        stream_name: Name of the stream this task relates to
        task_id: Unique identifier for the task
        task_name: Short name/title of the task
        description: Optional longer description

    Returns:
        The created task as a dictionary
    """
    logger.info(f"Inserting stream task at position {position} for {stream_name}: {task_id}")
    task = StreamTask(
        id=task_id,
        stream_name=stream_name,
        task_name=task_name,
        description=description,
    )
    position = max(0, min(position, len(_checklist.stream_tasks)))
    _checklist.stream_tasks.insert(position, task)
    return task.model_dump()


@mcp_tool(
    domain=ToolDomain.GUIDANCE,
)
def add_finalization_task(
    task_id: Annotated[str, Field(description="Unique identifier for the task")],
    task_name: Annotated[str, Field(description="Short name/title of the task")],
    description: Annotated[
        str | None,
        Field(description="Optional longer description with additional context/instructions"),
    ] = None,
) -> dict:
    """Add a new finalization task to the end of the finalization tasks list.

    Args:
        task_id: Unique identifier for the task
        task_name: Short name/title of the task
        description: Optional longer description

    Returns:
        The created task as a dictionary
    """
    logger.info(f"Adding finalization task: {task_id}")
    task = FinalizationTask(
        id=task_id,
        task_name=task_name,
        description=description,
    )
    _checklist.finalization_tasks.append(task)
    return task.model_dump()


@mcp_tool(
    domain=ToolDomain.GUIDANCE,
)
def insert_finalization_task(
    position: Annotated[int, Field(description="Position to insert the task (0-indexed)")],
    task_id: Annotated[str, Field(description="Unique identifier for the task")],
    task_name: Annotated[str, Field(description="Short name/title of the task")],
    description: Annotated[
        str | None,
        Field(description="Optional longer description with additional context/instructions"),
    ] = None,
) -> dict:
    """Insert a new finalization task at a specific position.

    Args:
        position: Position to insert the task (0-indexed)
        task_id: Unique identifier for the task
        task_name: Short name/title of the task
        description: Optional longer description

    Returns:
        The created task as a dictionary
    """
    logger.info(f"Inserting finalization task at position {position}: {task_id}")
    task = FinalizationTask(
        id=task_id,
        task_name=task_name,
        description=description,
    )
    position = max(0, min(position, len(_checklist.finalization_tasks)))
    _checklist.finalization_tasks.insert(position, task)
    return task.model_dump()


@mcp_tool(
    domain=ToolDomain.GUIDANCE,
)
def update_task_status(
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

    Args:
        task_id: Unique identifier for the task
        status: New status (not_started, in_progress, completed, blocked)
        status_detail: Optional details about the status change

    Returns:
        The updated task as a dictionary

    Raises:
        ValueError: If task_id is not found
    """
    logger.info(f"Updating task status for {task_id} to {status}")
    task = _checklist.get_task_by_id(task_id)
    if not task:
        raise ValueError(f"Task with ID '{task_id}' not found.")

    task.status = status
    task.status_detail = status_detail
    return task.model_dump()


@mcp_tool(
    domain=ToolDomain.GUIDANCE,
)
def remove_task(
    task_id: Annotated[str, Field(description="Unique identifier for the task")],
) -> dict:
    """Remove a task from the checklist.

    Args:
        task_id: Unique identifier for the task to remove

    Returns:
        Success message with the removed task details

    Raises:
        ValueError: If task_id is not found
    """
    logger.info(f"Removing task: {task_id}")
    task = _checklist.get_task_by_id(task_id)
    if not task:
        raise ValueError(f"Task with ID '{task_id}' not found.")

    if isinstance(task, ConnectorTask):
        _checklist.basic_connector_tasks.remove(task)
    elif isinstance(task, StreamTask):
        _checklist.stream_tasks.remove(task)
    elif isinstance(task, FinalizationTask):
        _checklist.finalization_tasks.remove(task)

    return {
        "success": True,
        "message": f"Task '{task_id}' removed successfully",
        "removed_task": task.model_dump(),
    }


@mcp_tool(
    domain=ToolDomain.GUIDANCE,
)
def reset_checklist() -> dict:
    """Reset the checklist to the default connector build task list.

    This will clear all tasks and restore the default set of connector build tasks.

    Returns:
        Success message with the new task list summary
    """
    global _checklist
    logger.info("Resetting checklist to default")
    _checklist = TaskList.new_connector_build_task_list()
    return {
        "success": True,
        "message": "Checklist reset to default connector build tasks",
        "summary": _checklist.get_summary(),
    }


def register_checklist_tools(
    app: FastMCP,
):
    """Register checklist tools in the MCP server."""
    register_mcp_tools(app, domain=ToolDomain.GUIDANCE)
