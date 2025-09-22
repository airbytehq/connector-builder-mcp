"""OpenAI Evals integration for connector readiness report evaluation.

This module provides functionality to evaluate connector readiness reports
against golden examples using OpenAI's evals framework, focusing on stream
enumeration and record counts as specified in the original requirements.
"""

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import openai


logger = logging.getLogger(__name__)


@dataclass
class GoldenExample:
    """Golden example for connector readiness evaluation."""

    api_name: str
    expected_streams: list[str]
    min_records_per_stream: dict[str, int] = field(default_factory=dict)
    max_acceptable_warnings: int = 5
    success_criteria: dict[str, Any] = field(default_factory=dict)
    description: str = ""


@dataclass
class EvalResult:
    """Result of an evaluation run."""

    eval_run_id: str
    status: str
    score: float | None = None
    details: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)


class ConnectorReadinessEvaluator:
    """Evaluates connector readiness reports using OpenAI evals framework."""

    def __init__(self, openai_client: openai.OpenAI | None = None):
        """Initialize the evaluator with OpenAI client."""
        if openai_client:
            self.client = openai_client
        else:
            try:
                self.client = openai.OpenAI()
            except openai.OpenAIError:
                self.client = None
        self.eval_id: str | None = None

    def create_eval_definition(
        self,
        eval_name: str = "connector-readiness-evaluation",
        description: str = "Evaluates connector readiness reports against golden examples",
    ) -> str:
        """Create an OpenAI eval definition for connector readiness assessment.

        Returns:
            The eval ID for the created evaluation
        """
        eval_definition = {
            "name": eval_name,
            "description": description,
            "data_source_config": {
                "type": "jsonl",
                "schema": {
                    "type": "object",
                    "properties": {
                        "input": {
                            "type": "object",
                            "properties": {
                                "api_name": {"type": "string"},
                                "readiness_report": {"type": "string"},
                                "golden_example": {
                                    "type": "object",
                                    "properties": {
                                        "expected_streams": {"type": "array"},
                                        "min_records_per_stream": {"type": "object"},
                                        "max_acceptable_warnings": {"type": "number"},
                                    },
                                },
                            },
                        },
                        "ideal": {"type": "string"},
                    },
                },
            },
            "testing_criteria": [
                {
                    "name": "stream_enumeration_accuracy",
                    "description": "Verify all expected streams are present in the report",
                    "weight": 0.4,
                },
                {
                    "name": "record_count_validation",
                    "description": "Check that record counts meet minimum thresholds",
                    "weight": 0.4,
                },
                {
                    "name": "warning_threshold_compliance",
                    "description": "Ensure warnings don't exceed acceptable limits",
                    "weight": 0.2,
                },
            ],
        }

        if not self.client:
            raise RuntimeError("OpenAI client not available - API key required")

        try:
            response = self.client.evals.create(**eval_definition)
            self.eval_id = response.id
            logger.info(f"Created eval definition: {self.eval_id}")
            return self.eval_id
        except Exception as e:
            logger.error(f"Failed to create eval definition: {e}")
            raise

    def parse_readiness_report(self, report_text: str) -> dict[str, Any]:
        """Parse a connector readiness report to extract structured data.

        Args:
            report_text: The markdown readiness report text

        Returns:
            Structured data extracted from the report
        """
        parsed_data = {
            "streams": {},
            "total_records": 0,
            "successful_streams": 0,
            "total_streams": 0,
            "warnings": [],
            "overall_success": False,
        }

        if "Successful Streams" in report_text:
            success_match = re.search(r"Successful Streams\*\*:\s*(\d+)/(\d+)", report_text)
            if success_match:
                parsed_data["successful_streams"] = int(success_match.group(1))
                parsed_data["total_streams"] = int(success_match.group(2))
        elif "streams successful" in report_text:
            success_match = re.search(r"(\d+)/(\d+)\s+streams successful", report_text)
            if success_match:
                parsed_data["successful_streams"] = int(success_match.group(1))
                parsed_data["total_streams"] = int(success_match.group(2))
        elif "Streams Tested" in report_text:
            tested_match = re.search(r"Streams Tested\*\*:\s*(\d+)\s+out\s+of\s+(\d+)", report_text)
            if tested_match:
                parsed_data["total_streams"] = int(tested_match.group(2))
            success_match = re.search(r"Successful Streams\*\*:\s*(\d+)/(\d+)", report_text)
            if success_match:
                parsed_data["successful_streams"] = int(success_match.group(1))

        records_match = re.search(r"Total Records Extracted\*\*:\s*([\d,]+)", report_text)
        if records_match:
            parsed_data["total_records"] = int(records_match.group(1).replace(",", ""))

        stream_sections = re.findall(r"### (.+?) ✅\n(.*?)(?=###|$)", report_text, re.DOTALL)

        if not stream_sections:
            sections = re.split(r"\n\s*\n", report_text.strip())
            stream_index = 0

            for section in sections:
                if "- **Records Extracted**:" in section:
                    stream_name = f"stream_{stream_index + 1}"
                    stream_sections.append((stream_name, section))
                    stream_index += 1

        for stream_name, section_content in stream_sections:
            stream_name = stream_name.strip()

            records_match = re.search(r"- \*\*Records Extracted\*\*:\s*([\d,]+)", section_content)
            records_count = int(records_match.group(1).replace(",", "")) if records_match else 0

            warnings = re.findall(r"⚠️[^⚠️]*", section_content)

            success = "No issues detected" in section_content

            parsed_data["streams"][stream_name] = {
                "records_count": records_count,
                "success": success,
                "warnings": warnings,
            }

        parsed_data["overall_success"] = (
            "FAILED" not in report_text.upper()
            and "failed" not in report_text.lower()
            and parsed_data["successful_streams"] > 0
            and parsed_data["successful_streams"] == parsed_data["total_streams"]
        )

        return parsed_data

    def evaluate_against_golden(
        self, report_text: str, golden_example: GoldenExample
    ) -> dict[str, Any]:
        """Evaluate a readiness report against a golden example.

        Args:
            report_text: The connector readiness report markdown
            golden_example: The golden example to compare against

        Returns:
            Evaluation results with scores and details
        """
        parsed_report = self.parse_readiness_report(report_text)

        evaluation = {
            "stream_enumeration_score": 0.0,
            "record_count_score": 0.0,
            "warning_threshold_score": 0.0,
            "overall_score": 0.0,
            "details": {},
            "passed_criteria": [],
            "failed_criteria": [],
        }

        expected_streams = set(golden_example.expected_streams)
        actual_streams = set(parsed_report["streams"].keys())

        if expected_streams:
            stream_intersection = expected_streams.intersection(actual_streams)
            evaluation["stream_enumeration_score"] = len(stream_intersection) / len(
                expected_streams
            )

            if evaluation["stream_enumeration_score"] >= 1.0:
                evaluation["passed_criteria"].append("All expected streams found")
            else:
                missing_streams = expected_streams - actual_streams
                evaluation["failed_criteria"].append(f"Missing streams: {list(missing_streams)}")

        record_scores = []
        for stream_name, min_records in golden_example.min_records_per_stream.items():
            if stream_name in parsed_report["streams"]:
                actual_records = parsed_report["streams"][stream_name]["records_count"]
                if actual_records >= min_records:
                    record_scores.append(1.0)
                    evaluation["passed_criteria"].append(
                        f"{stream_name}: {actual_records} >= {min_records} records"
                    )
                else:
                    record_scores.append(actual_records / min_records)
                    evaluation["failed_criteria"].append(
                        f"{stream_name}: {actual_records} < {min_records} records"
                    )
            else:
                record_scores.append(0.0)
                evaluation["failed_criteria"].append(f"{stream_name}: Stream not found")

        evaluation["record_count_score"] = (
            sum(record_scores) / len(record_scores) if record_scores else 0.0
        )

        total_warnings = sum(
            len(stream_data["warnings"]) for stream_data in parsed_report["streams"].values()
        )
        if total_warnings <= golden_example.max_acceptable_warnings:
            evaluation["warning_threshold_score"] = 1.0
            evaluation["passed_criteria"].append(
                f"Warnings within limit: {total_warnings} <= {golden_example.max_acceptable_warnings}"
            )
        else:
            evaluation["warning_threshold_score"] = max(
                0.0,
                1.0
                - (total_warnings - golden_example.max_acceptable_warnings)
                / golden_example.max_acceptable_warnings,
            )
            evaluation["failed_criteria"].append(
                f"Too many warnings: {total_warnings} > {golden_example.max_acceptable_warnings}"
            )

        evaluation["overall_score"] = (
            evaluation["stream_enumeration_score"] * 0.4
            + evaluation["record_count_score"] * 0.4
            + evaluation["warning_threshold_score"] * 0.2
        )

        evaluation["details"] = {
            "parsed_report": parsed_report,
            "golden_example": {
                "api_name": golden_example.api_name,
                "expected_streams": golden_example.expected_streams,
                "min_records_per_stream": golden_example.min_records_per_stream,
                "max_acceptable_warnings": golden_example.max_acceptable_warnings,
            },
        }

        return evaluation

    def create_eval_run(self, test_data_path: str | Path, eval_id: str | None = None) -> EvalResult:
        """Create and execute an eval run with test data.

        Args:
            test_data_path: Path to JSONL file with test data
            eval_id: Optional eval ID, uses self.eval_id if not provided

        Returns:
            EvalResult with run details
        """
        eval_id = eval_id or self.eval_id
        if not eval_id:
            raise ValueError("No eval ID provided and none set on evaluator")

        try:
            with open(test_data_path) as f:
                file_response = self.client.files.create(file=f, purpose="evals")

            run_response = self.client.evals.runs.create(
                eval_id=eval_id, data_source_config={"jsonl_file": file_response.id}
            )

            logger.info(f"Created eval run: {run_response.id}")

            return EvalResult(
                eval_run_id=run_response.id,
                status=run_response.status,
                details={"file_id": file_response.id},
            )

        except Exception as e:
            logger.error(f"Failed to create eval run: {e}")
            return EvalResult(eval_run_id="", status="failed", errors=[str(e)])

    def get_eval_results(self, eval_run_id: str) -> EvalResult:
        """Get results from a completed eval run.

        Args:
            eval_run_id: The eval run ID to check

        Returns:
            EvalResult with updated status and scores
        """
        try:
            run_response = self.client.evals.runs.retrieve(eval_run_id)

            result = EvalResult(eval_run_id=eval_run_id, status=run_response.status)

            if hasattr(run_response, "results") and run_response.results:
                result.score = run_response.results.get("overall_score")
                result.details = run_response.results

            return result

        except Exception as e:
            logger.error(f"Failed to get eval results: {e}")
            return EvalResult(eval_run_id=eval_run_id, status="error", errors=[str(e)])


def create_test_data_jsonl(golden_examples: list[GoldenExample], output_path: str | Path) -> None:
    """Create JSONL test data file from golden examples.

    Args:
        golden_examples: List of golden examples to convert
        output_path: Path where to save the JSONL file
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w") as f:
        for example in golden_examples:
            test_case = {
                "input": {
                    "api_name": example.api_name,
                    "readiness_report": "",  # Will be filled during actual evaluation
                    "golden_example": {
                        "expected_streams": example.expected_streams,
                        "min_records_per_stream": example.min_records_per_stream,
                        "max_acceptable_warnings": example.max_acceptable_warnings,
                    },
                },
                "ideal": f"PASS: All streams ({', '.join(example.expected_streams)}) present with sufficient records",
            }
            f.write(json.dumps(test_case) + "\n")

    logger.info(f"Created test data JSONL at {output_path}")


RICK_AND_MORTY_GOLDEN = GoldenExample(
    api_name="Rick and Morty API",
    expected_streams=["characters", "locations", "episodes"],
    min_records_per_stream={"characters": 20, "locations": 10, "episodes": 10},
    max_acceptable_warnings=3,
    success_criteria={"min_total_records": 40, "max_duration_seconds": 120},
    description="Rick and Morty API connector evaluation baseline",
)

JSONPLACEHOLDER_GOLDEN = GoldenExample(
    api_name="JSONPlaceholder API",
    expected_streams=["posts", "comments", "users"],
    min_records_per_stream={"posts": 50, "comments": 100, "users": 5},
    max_acceptable_warnings=2,
    success_criteria={"min_total_records": 155, "max_duration_seconds": 60},
    description="JSONPlaceholder API connector evaluation baseline",
)

DEFAULT_GOLDEN_EXAMPLES = [RICK_AND_MORTY_GOLDEN, JSONPLACEHOLDER_GOLDEN]
