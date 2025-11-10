"""Checklist domain models and utilities.

This module contains the core domain models and persistence logic for the checklist system.
The MCP integration layer is in mcp/checklist.py.
"""

import json
import logging
from enum import Enum

from pydantic import BaseModel, Field

from connector_builder_mcp._paths import get_session_checklist_path


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
    SPECIAL_REQUIREMENTS = "special_requirements"
    ACCEPTANCE_TESTS = "acceptance_tests"
    FINALIZATION = "finalization"


class Task(BaseModel):
    """Base task model with common fields."""

    task_type: TaskTypeEnum = Field(
        description="Type of task (connector, stream, special_requirements, acceptance_tests, or finalization)"
    )
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


class SpecialRequirementTask(Task):
    """Special requirement task for custom connector-specific requirements."""

    task_type: TaskTypeEnum = TaskTypeEnum.SPECIAL_REQUIREMENTS


class AcceptanceTestsTask(Task):
    """Acceptance tests task for testing and validation."""

    task_type: TaskTypeEnum = TaskTypeEnum.ACCEPTANCE_TESTS


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
    special_requirements: list[SpecialRequirementTask] = Field(
        default_factory=list,
        description="List of special requirement tasks",
    )
    acceptance_tests: list[AcceptanceTestsTask] = Field(
        default_factory=list,
        description="List of acceptance test tasks",
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
        result.extend(self.special_requirements)
        result.extend(self.acceptance_tests)
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
            special_requirements=[],
            acceptance_tests=[],
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


def load_session_checklist(session_id: str) -> TaskList:
    """Load the checklist from the session directory.

    Args:
        session_id: Session ID

    Returns:
        TaskList loaded from disk, or default task list if file doesn't exist
    """
    checklist_path = get_session_checklist_path(session_id)

    if not checklist_path.exists():
        logger.debug(f"Session checklist does not exist at: {checklist_path}, returning default")
        return TaskList.new_connector_build_task_list()

    try:
        content = checklist_path.read_text(encoding="utf-8")
        data = json.loads(content)
        checklist = TaskList.model_validate(data)
        logger.info(f"Loaded session checklist from: {checklist_path}")
        return checklist
    except Exception as e:
        logger.error(f"Error loading session checklist from {checklist_path}: {e}")
        logger.info("Returning default task list")
        return TaskList.new_connector_build_task_list()


def save_session_checklist(session_id: str, checklist: TaskList) -> None:
    """Save the checklist to the session directory.

    Args:
        session_id: Session ID
        checklist: TaskList to save
    """
    checklist_path = get_session_checklist_path(session_id)

    checklist_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)

    temp_path = checklist_path.with_suffix(".tmp")
    try:
        content = json.dumps(checklist.model_dump(), indent=2, ensure_ascii=False)
        temp_path.write_text(content, encoding="utf-8")
        temp_path.replace(checklist_path)
        logger.info(f"Saved session checklist to: {checklist_path}")
    except Exception as e:
        logger.error(f"Error saving session checklist to {checklist_path}: {e}")
        if temp_path.exists():
            temp_path.unlink()
        raise


def add_special_requirements_to_checklist(
    checklist: TaskList,
    requirements: list[str],
) -> list[dict]:
    """Add special requirement tasks to a checklist.

    Args:
        checklist: TaskList to add requirements to
        requirements: List of requirement descriptions

    Returns:
        List of added task dictionaries
    """
    added_tasks = []
    for req in requirements:
        slug = req.lower().replace(" ", "-")
        slug = "".join(c for c in slug if c.isalnum() or c == "-")
        slug = slug[:50]

        base_slug = slug
        counter = 1
        while any(t.id == slug for t in checklist.special_requirements):
            slug = f"{base_slug}-{counter}"
            counter += 1

        task = SpecialRequirementTask(
            id=slug,
            task_name=req,
            description=None,
        )
        checklist.special_requirements.append(task)
        added_tasks.append(task.model_dump())

    return added_tasks
