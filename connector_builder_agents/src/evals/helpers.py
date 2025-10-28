# Copyright (c) 2025 Airbyte, Inc., all rights reserved.


from collections.abc import Mapping
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from connector_builder_agents.src.agents import ManagerTaskOutput


class ConnectorBuilderEvalTaskOutput(BaseModel):
    workspace_dir: Path
    success: bool
    final_output: ManagerTaskOutput | None
    num_turns: int
    artifacts: Mapping[str, Any]


def get_artifact(workspace_dir, artifact_name: str, logger) -> str | None:
    """Read an artifact file from the workspace directory."""
    artifact_path = workspace_dir / artifact_name
    if artifact_path.exists():
        content = artifact_path.read_text(encoding="utf-8")
        logger.info(f"Found {artifact_name} ({len(content)} characters)")
        return content
    else:
        logger.warning(f"No {artifact_name} found")
        return None


def create_connector_builder_eval_task_output(output: dict) -> ConnectorBuilderEvalTaskOutput:
    """Create a ConnectorBuilderEvalTaskOutput from a dictionary."""

    if output.get("final_output", None):
        final_output_data = output.get("final_output", {})
        if isinstance(final_output_data, ManagerTaskOutput):
            manager_iteration_output = final_output_data
        elif isinstance(final_output_data, dict):
            manager_iteration_output = ManagerTaskOutput(**final_output_data)
        else:
            # Handle other types (e.g., string) - set to None
            manager_iteration_output = None
        output.pop("final_output")
    else:
        manager_iteration_output = None

    return ConnectorBuilderEvalTaskOutput(**output, final_output=manager_iteration_output)
