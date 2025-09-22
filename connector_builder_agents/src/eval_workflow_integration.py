"""Workflow integration for automatic connector readiness evaluation.

This module integrates OpenAI evals with the existing connector build workflow
by hooking into job completion events and automatically evaluating generated
readiness reports against golden examples.
"""

import logging
from pathlib import Path
from typing import Any

from .constants import WORKSPACE_WRITE_DIR
from .evals_integration import (
    DEFAULT_GOLDEN_EXAMPLES,
    ConnectorReadinessEvaluator,
    GoldenExample,
)


logger = logging.getLogger(__name__)


class EvalWorkflowManager:
    """Manages automatic evaluation of connector readiness reports."""

    def __init__(self, workspace_dir: Path = WORKSPACE_WRITE_DIR):
        """Initialize the eval workflow manager."""
        self.workspace_dir = workspace_dir
        self.evaluator = ConnectorReadinessEvaluator()
        self.eval_results_dir = workspace_dir / "eval_results"
        self.eval_results_dir.mkdir(parents=True, exist_ok=True)

    def find_readiness_report(self) -> Path | None:
        """Find the most recent connector readiness report in the workspace.

        Returns:
            Path to the readiness report file, or None if not found
        """
        report_files = list(self.workspace_dir.rglob("connector-readiness-report.md"))

        if report_files:
            return max(report_files, key=lambda p: p.stat().st_mtime)

        md_files = list(self.workspace_dir.rglob("*.md"))
        for md_file in md_files:
            if "readiness" in md_file.name.lower() or "report" in md_file.name.lower():
                return md_file

        return None

    def determine_golden_example(
        self, api_name: str | None = None, report_content: str = ""
    ) -> GoldenExample | None:
        """Determine which golden example to use based on API name or report content.

        Args:
            api_name: The API name if available
            report_content: The readiness report content for analysis

        Returns:
            Matching golden example or None if no match found
        """
        if not api_name and not report_content:
            return None

        if api_name:
            api_name_lower = api_name.lower()
            for golden in DEFAULT_GOLDEN_EXAMPLES:
                if (
                    golden.api_name.lower() in api_name_lower
                    or api_name_lower in golden.api_name.lower()
                ):
                    return golden

        if report_content:
            content_lower = report_content.lower()

            if any(
                indicator in content_lower
                for indicator in ["rick", "morty", "character", "location", "episode"]
            ):
                return next(
                    (g for g in DEFAULT_GOLDEN_EXAMPLES if "rick" in g.api_name.lower()), None
                )

            if any(
                indicator in content_lower
                for indicator in ["jsonplaceholder", "posts", "comments", "users"]
            ):
                return next(
                    (g for g in DEFAULT_GOLDEN_EXAMPLES if "jsonplaceholder" in g.api_name.lower()),
                    None,
                )

        return DEFAULT_GOLDEN_EXAMPLES[0] if DEFAULT_GOLDEN_EXAMPLES else None

    def run_evaluation(
        self, api_name: str | None = None, trace_id: str | None = None
    ) -> dict[str, Any] | None:
        """Run evaluation on the most recent readiness report.

        Args:
            api_name: Optional API name for golden example selection
            trace_id: Optional trace ID for correlation

        Returns:
            Evaluation results or None if no report found
        """
        report_path = self.find_readiness_report()
        if not report_path:
            logger.warning("No readiness report found for evaluation")
            return None

        try:
            report_content = report_path.read_text(encoding="utf-8")
        except Exception as e:
            logger.error(f"Failed to read readiness report: {e}")
            return None

        golden_example = self.determine_golden_example(api_name, report_content)
        if not golden_example:
            logger.warning("No matching golden example found for evaluation")
            return None

        logger.info(f"Running evaluation against golden example: {golden_example.api_name}")

        try:
            evaluation_result = self.evaluator.evaluate_against_golden(
                report_content, golden_example
            )

            evaluation_result["metadata"] = {
                "report_path": str(report_path),
                "api_name": api_name,
                "trace_id": trace_id,
                "golden_example_used": golden_example.api_name,
            }

            results_file = self.eval_results_dir / f"evaluation_{trace_id or 'unknown'}.json"
            import json

            with results_file.open("w") as f:
                json.dump(evaluation_result, f, indent=2, default=str)

            overall_score = evaluation_result.get("overall_score", 0.0)
            logger.info(f"Evaluation completed. Overall score: {overall_score:.2f}")
            logger.info(f"Results saved to: {results_file}")

            return evaluation_result

        except Exception as e:
            logger.error(f"Evaluation failed: {e}")
            return None

    def generate_evaluation_summary(self, evaluation_result: dict[str, Any]) -> str:
        """Generate a human-readable summary of evaluation results.

        Args:
            evaluation_result: The evaluation result dictionary

        Returns:
            Formatted summary string
        """
        if not evaluation_result:
            return "❌ No evaluation results available"

        overall_score = evaluation_result.get("overall_score", 0.0)

        if overall_score >= 0.9:
            status_emoji = "✅"
            status_text = "EXCELLENT"
        elif overall_score >= 0.7:
            status_emoji = "🟡"
            status_text = "GOOD"
        elif overall_score >= 0.5:
            status_emoji = "🟠"
            status_text = "NEEDS IMPROVEMENT"
        else:
            status_emoji = "❌"
            status_text = "POOR"

        lines = [
            "=" * 60,
            "📊 CONNECTOR READINESS EVALUATION SUMMARY",
            "=" * 60,
            f"{status_emoji} Overall Score: {overall_score:.1%} ({status_text})",
            "",
            "📈 Component Scores:",
            f"  • Stream Enumeration: {evaluation_result.get('stream_enumeration_score', 0):.1%}",
            f"  • Record Count Validation: {evaluation_result.get('record_count_score', 0):.1%}",
            f"  • Warning Threshold: {evaluation_result.get('warning_threshold_score', 0):.1%}",
            "",
        ]

        passed_criteria = evaluation_result.get("passed_criteria", [])
        if passed_criteria:
            lines.append("✅ Passed Criteria:")
            for criterion in passed_criteria[:5]:  # Limit to first 5
                lines.append(f"  • {criterion}")
            if len(passed_criteria) > 5:
                lines.append(f"  • ... and {len(passed_criteria) - 5} more")
            lines.append("")

        failed_criteria = evaluation_result.get("failed_criteria", [])
        if failed_criteria:
            lines.append("❌ Failed Criteria:")
            for criterion in failed_criteria[:5]:  # Limit to first 5
                lines.append(f"  • {criterion}")
            if len(failed_criteria) > 5:
                lines.append(f"  • ... and {len(failed_criteria) - 5} more")
            lines.append("")

        metadata = evaluation_result.get("metadata", {})
        if metadata:
            lines.append("ℹ️ Evaluation Details:")
            if metadata.get("golden_example_used"):
                lines.append(f"  • Golden Example: {metadata['golden_example_used']}")
            if metadata.get("api_name"):
                lines.append(f"  • API Name: {metadata['api_name']}")
            if metadata.get("trace_id"):
                lines.append(f"  • Trace ID: {metadata['trace_id']}")

        lines.append("=" * 60)

        return "\n".join(lines)


_eval_workflow_manager: EvalWorkflowManager | None = None


def get_eval_workflow_manager() -> EvalWorkflowManager:
    """Get or create the global eval workflow manager instance."""
    global _eval_workflow_manager
    if _eval_workflow_manager is None:
        _eval_workflow_manager = EvalWorkflowManager()
    return _eval_workflow_manager


def trigger_automatic_evaluation(
    api_name: str | None = None, trace_id: str | None = None
) -> dict[str, Any] | None:
    """Trigger automatic evaluation of the most recent readiness report.

    This function is designed to be called from workflow completion hooks
    like mark_job_success() to automatically evaluate connector readiness.

    Args:
        api_name: Optional API name for golden example selection
        trace_id: Optional trace ID for correlation

    Returns:
        Evaluation results or None if evaluation failed
    """
    try:
        manager = get_eval_workflow_manager()
        return manager.run_evaluation(api_name=api_name, trace_id=trace_id)
    except Exception as e:
        logger.error(f"Automatic evaluation failed: {e}")
        return None
