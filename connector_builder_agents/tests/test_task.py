# Copyright (c) 2025 Airbyte, Inc., all rights reserved.

import json
from pathlib import Path
from unittest.mock import ANY, MagicMock, patch

import pytest
from pydantic_ai.run import AgentRunResult

from connector_builder_agents.src.constants import DEFAULT_DEVELOPER_MODEL, DEFAULT_MANAGER_MODEL
from connector_builder_agents.src.evals.task import (
    ConnectorBuilderEvalTaskOutput,
    run_connector_build_task,
)


class TestConnectorBuilderTask:
    """Test the run_connector_build_task function."""

    @pytest.mark.asyncio
    async def test_run_connector_build_task_success(self):
        """Test successful execution of run_connector_build_task with mocked dependencies."""
        dataset_row = {
            "input": json.dumps({"name": "test-connector", "prompt_name": "test-prompt"})
        }

        mock_run_result = MagicMock(spec=AgentRunResult)
        mock_run_result.output = "Test build completed successfully"
        mock_build_result = [mock_run_result]

        mock_workspace_dir = MagicMock(spec=Path)
        mock_workspace_dir.absolute.return_value = Path(
            "/absolute/test/workspace/eval-test-connector-1234567890"
        )

        # Mock artifact content
        mock_readiness_report = "Test readiness report content"
        mock_manifest = "Test manifest content"

        with (
            patch("connector_builder_agents.src.evals.task.run_connector_build") as mock_run_build,
            patch(
                "connector_builder_agents.src.evals.task.get_workspace_dir"
            ) as mock_get_workspace,
            patch("connector_builder_agents.src.evals.task.get_artifact") as mock_get_artifact,
            patch("connector_builder_agents.src.evals.task.time.time") as mock_time,
        ):
            mock_time.return_value = 1234567890
            mock_run_build.return_value = mock_build_result
            mock_get_workspace.return_value = mock_workspace_dir
            mock_get_artifact.side_effect = [mock_readiness_report, mock_manifest]

            result = await run_connector_build_task(dataset_row)

            assert isinstance(result, ConnectorBuilderEvalTaskOutput)
            assert result.workspace_dir == Path(
                "/absolute/test/workspace/eval-test-connector-1234567890"
            )
            assert result.success is True
            assert result.final_output == "Test build completed successfully"
            assert result.num_turns == 1
            assert result.artifacts["readiness_report"] == mock_readiness_report
            assert result.artifacts["manifest"] == mock_manifest

            expected_session_id = "eval-test-connector-1234567890"
            mock_run_build.assert_called_once_with(
                api_name="test-prompt",
                session_id=expected_session_id,
                developer_model=DEFAULT_DEVELOPER_MODEL,
                manager_model=DEFAULT_MANAGER_MODEL,
            )
            mock_get_workspace.assert_called_once_with(expected_session_id)
            assert mock_get_artifact.call_count == 2
            mock_get_artifact.assert_any_call(
                mock_workspace_dir, "connector-readiness-report.md", ANY
            )
            mock_get_artifact.assert_any_call(mock_workspace_dir, "manifest.yaml", ANY)
