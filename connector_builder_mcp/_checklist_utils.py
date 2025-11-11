"""Checklist domain models and utilities.

This module contains the core domain models and persistence logic for the checklist system.
The MCP integration layer is in mcp/checklist.py.
"""

import json
import logging
from enum import Enum
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field

from connector_builder_mcp._paths import get_global_checklist_path, get_session_checklist_path


logger = logging.getLogger(__name__)


class TaskStatusEnum(str, Enum):
    """Status of a task in the task list."""

    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    BLOCKED = "blocked"


class Task(BaseModel):
    """Task model with ID, name, description, and status tracking."""

    model_config = ConfigDict(extra="ignore")

    id: str = Field(description="Unique identifier for the task")
    name: str = Field(description="Short name/title of the task")
    description: str | None = Field(
        default=None,
        description="Optional longer description with additional context/instructions",
    )
    status: TaskStatusEnum = TaskStatusEnum.NOT_STARTED
    status_detail: str | None = Field(
        default=None,
        description="Details about the task status. Can be set when marking task as completed, blocked, or in progress to provide context.",
    )


class TaskList(BaseModel):
    """Generic task list for tracking progress."""

    basic_connector_tasks: list[Task] = Field(
        default_factory=list,
        description="List of basic connector tasks",
    )
    stream_tasks: dict[str, list[Task]] = Field(
        default_factory=dict,
        description="Dict of stream tasks, keyed by stream name",
    )
    stream_tasks_template: list[Task] = Field(
        default_factory=list,
        description="List of stream task to use for enumerated streams",
    )
    special_requirements: list[Task] = Field(
        default_factory=list,
        description="List of special requirement tasks",
    )
    acceptance_tests: list[Task] = Field(
        default_factory=list,
        description="List of acceptance test tasks",
    )
    finalization_tasks: list[Task] = Field(
        default_factory=list,
        description="List of finalization tasks",
    )

    @property
    def tasks(self) -> list[Task]:
        """Get all tasks combined from all task lists."""
        result: list[Task] = []
        result.extend(self.basic_connector_tasks)
        for stream_task_list in self.stream_tasks.values():
            result.extend(stream_task_list)
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

    def get_next_tasks(self, n: int = 1) -> list[Task]:
        """Get the next N tasks that are not yet completed.

        Prioritizes in-progress tasks before not-started tasks, using the order
        they appear in the task list (YAML order).

        Args:
            n: Number of tasks to return

        Returns:
            List of up to N tasks that are in progress or not started
        """
        all_tasks = self.tasks
        in_progress = [t for t in all_tasks if t.status == TaskStatusEnum.IN_PROGRESS]
        not_started = [t for t in all_tasks if t.status == TaskStatusEnum.NOT_STARTED]
        return (in_progress + not_started)[:n]

    def get_blocked_tasks(self) -> list[Task]:
        """Get all tasks that are currently blocked.

        Returns:
            List of tasks with BLOCKED status
        """
        return [t for t in self.tasks if t.status == TaskStatusEnum.BLOCKED]

    @classmethod
    def new_connector_build_task_list(cls) -> "TaskList":
        """Create a new task list with default connector build tasks from YAML file."""
        yaml_path: Path = get_global_checklist_path()

        with open(yaml_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)

        def _task_from_dict(task_dict: dict) -> Task:
            """Convert a task dict from YAML to a Task object."""
            return Task(
                id=task_dict["id"],
                name=task_dict["name"],
                description=task_dict.get("description"),
            )

        basic_connector_tasks = [
            _task_from_dict(task) for task in data.get("basic_connector_tasks", [])
        ]
        stream_tasks_template = [_task_from_dict(task) for task in data.get("stream_tasks", [])]
        special_requirements = [
            _task_from_dict(task) for task in data.get("special_requirements", [])
        ]

        acceptance_tests = [_task_from_dict(task) for task in data.get("acceptance_tests", [])]

        finalization_tasks = [_task_from_dict(task) for task in data.get("finalization_tasks", [])]

        return cls(
            basic_connector_tasks=basic_connector_tasks,
            stream_tasks_template=stream_tasks_template,
            stream_tasks={},
            special_requirements=special_requirements,
            acceptance_tests=acceptance_tests,
            finalization_tasks=finalization_tasks,
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

        if "stream_tasks" in data and isinstance(data["stream_tasks"], list):
            logger.warning("Migrating old stream_tasks list format to dict format")
            data["stream_tasks"] = {}

        for task_list_key in [
            "basic_connector_tasks",
            "special_requirements",
            "acceptance_tests",
            "finalization_tasks",
        ]:
            if task_list_key in data:
                for task in data[task_list_key]:
                    task.pop("task_type", None)
                    task.pop("stream_name", None)
                    if "task_name" in task and "name" not in task:
                        task["name"] = task.pop("task_name")

        if "stream_tasks" in data and isinstance(data["stream_tasks"], dict):
            for _stream_name, tasks in data["stream_tasks"].items():
                for task in tasks:
                    task.pop("task_type", None)
                    task.pop("stream_name", None)
                    if "task_name" in task and "name" not in task:
                        task["name"] = task.pop("task_name")

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


def _slugify(text: str, max_length: int = 50) -> str:
    """Convert text to a URL-safe slug.

    Args:
        text: Text to slugify
        max_length: Maximum length of the slug

    Returns:
        Slugified text
    """
    slug = text.lower().replace(" ", "-")
    slug = "".join(c for c in slug if c.isalnum() or c == "-")
    return slug[:max_length]


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
        slug = _slugify(req)

        base_slug = slug
        counter = 1
        while any(t.id == slug for t in checklist.special_requirements):
            slug = f"{base_slug}-{counter}"
            counter += 1

        task = Task(
            id=slug,
            name=req,
            description=None,
        )
        checklist.special_requirements.append(task)
        added_tasks.append(task.model_dump())

    return added_tasks


def register_stream_tasks(
    checklist: TaskList,
    stream_names: list[str],
) -> tuple[list[str], dict[str, str]]:
    """Register stream tasks for the given stream names.

    For each stream name, copies all stream task templates from the YAML file
    and adds them to the checklist with unique IDs (stream_slug:task_id).

    Args:
        checklist: TaskList to add stream tasks to
        stream_names: List of stream names to register

    Returns:
        Tuple of (added_streams, skipped_streams_with_reasons)
    """
    templates = checklist.stream_tasks_template
    if not templates:
        logger.warning("No stream task templates found in checklist")
        return [], {}

    added = []
    skipped = {}

    for stream_name in stream_names:
        if stream_name in checklist.stream_tasks:
            skipped[stream_name] = "already registered"
            continue

        stream_slug = _slugify(stream_name)
        stream_tasks = []

        for template in templates:
            task = Task(
                id=f"{stream_slug}:{template.id}",
                name=template.name,
                description=template.description,
                status=TaskStatusEnum.NOT_STARTED,
            )
            stream_tasks.append(task)

        checklist.stream_tasks[stream_name] = stream_tasks
        added.append(stream_name)

    return added, skipped
