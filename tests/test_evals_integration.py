"""Tests for OpenAI evals integration."""

import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

from connector_builder_agents.src.eval_workflow_integration import (
    EvalWorkflowManager,
    trigger_automatic_evaluation,
)
from connector_builder_agents.src.evals_integration import (
    ConnectorReadinessEvaluator,
    RICK_AND_MORTY_GOLDEN,
    create_test_data_jsonl,
)


SAMPLE_READINESS_REPORT = """

- **Streams Tested**: 3 out of 3 total streams
- **Successful Streams**: 3/3
- **Total Records Extracted**: 45
- **Total Duration**: 12.34s

- **Records Extracted**: 25
- **Duration**: 5.67s
- **Status**: No issues detected

- **Records Extracted**: 15
- **Duration**: 3.45s
- **Warnings**: ⚠️ Record count is multiple of 10 - may indicate pagination limit

- **Records Extracted**: 5
- **Duration**: 2.22s
- **Status**: No issues detected
"""

SAMPLE_FAILED_REPORT = """
**Status**: 1/3 streams successful
**Failed streams**: locations, episodes
**Total duration**: 15.67s

- **characters**: Connection timeout
- **locations**: Authentication failed
"""


class TestConnectorReadinessEvaluator:
    """Test the ConnectorReadinessEvaluator class."""

    def test_parse_readiness_report_success(self):
        """Test parsing a successful readiness report."""
        evaluator = ConnectorReadinessEvaluator()
        parsed = evaluator.parse_readiness_report(SAMPLE_READINESS_REPORT)

        assert parsed["overall_success"] is True
        assert parsed["successful_streams"] == 3
        assert parsed["total_streams"] == 3
        assert parsed["total_records"] == 45

        assert "characters" in parsed["streams"]
        assert parsed["streams"]["characters"]["records_count"] == 25
        assert parsed["streams"]["characters"]["success"] is True

        assert "locations" in parsed["streams"]
        assert parsed["streams"]["locations"]["records_count"] == 15
        assert len(parsed["streams"]["locations"]["warnings"]) > 0

    def test_parse_readiness_report_failure(self):
        """Test parsing a failed readiness report."""
        evaluator = ConnectorReadinessEvaluator()
        parsed = evaluator.parse_readiness_report(SAMPLE_FAILED_REPORT)

        assert parsed["overall_success"] is False
        assert parsed["successful_streams"] == 1
        assert parsed["total_streams"] == 3

    def test_evaluate_against_golden_success(self):
        """Test evaluation against golden example with successful report."""
        evaluator = ConnectorReadinessEvaluator()

        evaluation = evaluator.evaluate_against_golden(
            SAMPLE_READINESS_REPORT, RICK_AND_MORTY_GOLDEN
        )

        assert evaluation["stream_enumeration_score"] == 1.0  # All expected streams present
        assert evaluation["overall_score"] > 0.8  # Should be high overall score
        assert len(evaluation["passed_criteria"]) > 0

    def test_evaluate_against_golden_failure(self):
        """Test evaluation against golden example with failed report."""
        evaluator = ConnectorReadinessEvaluator()

        evaluation = evaluator.evaluate_against_golden(SAMPLE_FAILED_REPORT, RICK_AND_MORTY_GOLDEN)

        assert evaluation["overall_score"] < 0.5
        assert len(evaluation["failed_criteria"]) > 0


class TestEvalWorkflowManager:
    """Test the EvalWorkflowManager class."""

    def test_determine_golden_example_by_api_name(self):
        """Test golden example selection by API name."""
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = EvalWorkflowManager(workspace_dir=Path(temp_dir))

            golden = manager.determine_golden_example(api_name="Rick and Morty API")
            assert golden is not None
            assert "rick" in golden.api_name.lower()

            golden = manager.determine_golden_example(api_name="JSONPlaceholder")
            assert golden is not None
            assert "jsonplaceholder" in golden.api_name.lower()

    def test_determine_golden_example_by_content(self):
        """Test golden example selection by report content."""
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = EvalWorkflowManager(workspace_dir=Path(temp_dir))

            golden = manager.determine_golden_example(
                report_content="### characters ✅\n### locations ✅"
            )
            assert golden is not None
            assert "rick" in golden.api_name.lower()

    def test_find_readiness_report(self):
        """Test finding readiness reports in workspace."""
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            manager = EvalWorkflowManager(workspace_dir=workspace)

            report_file = workspace / "connector-readiness-report.md"
            report_file.write_text(SAMPLE_READINESS_REPORT)

            found_report = manager.find_readiness_report()
            assert found_report is not None
            assert found_report.name == "connector-readiness-report.md"

    def test_run_evaluation(self):
        """Test running evaluation workflow."""
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)

            mock_evaluator = Mock()
            mock_evaluator.evaluate_against_golden.return_value = {
                "overall_score": 0.85,
                "stream_enumeration_score": 1.0,
                "record_count_score": 0.8,
                "warning_threshold_score": 0.9,
                "passed_criteria": ["All streams found"],
                "failed_criteria": [],
            }

            manager = EvalWorkflowManager(workspace_dir=workspace)
            manager.evaluator = mock_evaluator

            report_file = workspace / "connector-readiness-report.md"
            report_file.write_text(SAMPLE_READINESS_REPORT)

            result = manager.run_evaluation(api_name="Rick and Morty API")

            assert result is not None
            assert result["overall_score"] == 0.85
            assert "metadata" in result
            mock_evaluator.evaluate_against_golden.assert_called_once()


class TestGoldenExamples:
    """Test golden example definitions."""

    def test_rick_and_morty_golden(self):
        """Test Rick and Morty golden example."""
        golden = RICK_AND_MORTY_GOLDEN

        assert golden.api_name == "Rick and Morty API"
        assert "characters" in golden.expected_streams
        assert "locations" in golden.expected_streams
        assert "episodes" in golden.expected_streams
        assert golden.min_records_per_stream["characters"] == 20

    def test_create_test_data_jsonl(self):
        """Test creating JSONL test data."""
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "test_data.jsonl"

            create_test_data_jsonl([RICK_AND_MORTY_GOLDEN], output_path)

            assert output_path.exists()

            with output_path.open() as f:
                line = f.readline()
                data = json.loads(line)

                assert "input" in data
                assert "ideal" in data
                assert data["input"]["api_name"] == "Rick and Morty API"
                assert "golden_example" in data["input"]


class TestWorkflowIntegration:
    """Test workflow integration functions."""

    @patch("connector_builder_agents.src.eval_workflow_integration.EvalWorkflowManager")
    def test_trigger_automatic_evaluation(self, mock_manager_class):
        """Test automatic evaluation trigger."""
        mock_manager = Mock()
        mock_manager.run_evaluation.return_value = {"overall_score": 0.9}
        mock_manager_class.return_value = mock_manager

        result = trigger_automatic_evaluation(api_name="Test API", trace_id="test-trace-123")

        assert result is not None
        assert result["overall_score"] == 0.9
        mock_manager.run_evaluation.assert_called_once_with(
            api_name="Test API", trace_id="test-trace-123"
        )

    @patch("connector_builder_agents.src.eval_workflow_integration.get_eval_workflow_manager")
    def test_trigger_automatic_evaluation_failure(self, mock_get_manager):
        """Test automatic evaluation trigger with failure."""
        mock_manager = Mock()
        mock_manager.run_evaluation.side_effect = Exception("Test error")
        mock_get_manager.return_value = mock_manager

        result = trigger_automatic_evaluation()

        assert result is None  # Should return None on failure
