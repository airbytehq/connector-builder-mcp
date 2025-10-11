# Copyright (c) 2025 Airbyte, Inc., all rights reserved.
"""Evaluators for connector builder agents."""

import json
import logging
import re
from collections.abc import Callable
from typing import Any

import pandas as pd
import yaml
from dotenv import load_dotenv
from opentelemetry.trace import get_current_span
from phoenix.evals import OpenAIModel, llm_classify


load_dotenv()

logger = logging.getLogger(__name__)

READINESS_EVAL_MODEL = "gpt-4o"
READINESS_EVAL_TEMPLATE = """You are evaluating whether a connector readiness test passed or failed.

A passing report should have all of the following:
- All streams tested successfully (marked with ✅)
- No critical errors or failures
- Records extracted from streams (even if with warnings)
- Successful completion indicated

A failing report could have any of the following:
- Streams marked as failed (❌)
- Critical errors preventing extraction
- Zero records extracted from streams
- Error messages indicating failure

Based on the connector readiness report below, classify whether the test PASSED or FAILED. Your answer should be a single word, either "PASSED" or "FAILED".

{readiness_report}
"""


def _parse_expected_streams_dict(expected: dict, having: str | None = None) -> dict:
    """Parse and return expected streams as a dict mapping stream_name -> stream_config.

    Args:
        expected: The expected dictionary containing stream configurations
        having: Optional key name to filter streams - only returns streams where this key exists
    """
    expected_obj = json.loads(expected.get("expected", "{}"))
    expected_streams = expected_obj.get("expected_streams", [])

    result = {}
    for stream_obj in expected_streams:
        if isinstance(stream_obj, dict):
            result.update(stream_obj)
        elif isinstance(stream_obj, str):
            result[stream_obj] = {}

    if having is not None:
        result = {name: config for name, config in result.items() if config.get(having) is not None}

    return result


def _get_manifest_streams(output: dict) -> list | None:
    """Extract and parse the manifest streams from output artifacts."""
    if output is None:
        return None

    manifest_str = output.get("artifacts", {}).get("manifest", None)
    if manifest_str is None:
        return None

    manifest = yaml.safe_load(manifest_str)
    return manifest.get("streams", [])


def _get_readiness_report(output: dict) -> str | None:
    """Extract the readiness report from output artifacts."""
    if output is None:
        return None

    return output.get("artifacts", {}).get("readiness_report", None)


def readiness_eval(output: dict) -> int:
    """Create Phoenix LLM classifier for readiness evaluation. Return 1 if PASSED, 0 if FAILED."""
    readiness_report = _get_readiness_report(output)
    if readiness_report is None:
        logger.warning("No readiness report found")
        return 0

    rails = ["PASSED", "FAILED"]

    eval_df = llm_classify(
        model=OpenAIModel(model=READINESS_EVAL_MODEL),
        data=pd.DataFrame([{"readiness_report": readiness_report}]),
        template=READINESS_EVAL_TEMPLATE,
        rails=rails,
        provide_explanation=True,
    )

    logger.info(f"Readiness evaluation result: {eval_df}")

    label = eval_df["label"][0]
    score = 1 if label.upper() == "PASSED" else 0

    return score


def stream_names_eval(expected: dict, output: dict) -> float:
    """Evaluate if all expected streams were built. Return the percentage of expected streams that are present in available streams."""
    return _eval_expected_stream_props(
        expected_stream_props=_parse_expected_streams_dict(expected),
        output_stream_props={
            stream.get("name", "(undeclared)"): stream
            for stream in _get_manifest_streams(output) or []
        },
        prop="name",
    )


def _eval_expected_stream_props(
    *,
    expected_stream_props: dict[str, Any],
    output_stream_props: dict[str, Any],
    prop: str,
    eval_fn: Callable[[Any, Any], bool] = lambda expected, actual: expected == actual,
    span: Any | None = None,  # TODO: replace `Any` with proper type
) -> float:
    """Generic evaluator for expected stream properties."""
    matched_count = 0
    total_count = len(expected_stream_props)

    for stream_name, expected_props in expected_stream_props.items():
        expected_value = expected_props.get(prop)
        actual_value = output_stream_props.get(stream_name, {}).get(prop)

        if expected_value is None:
            continue

        if eval_fn(expected_value, actual_value):
            matched_count += 1
            logger.info(f"✓ {stream_name}: {prop} matches {expected_value}")
        else:
            logger.warning(
                f"✗ {stream_name}: {prop} mismatch - expected {expected_value}, got {actual_value}"
            )

    span = get_current_span()
    span.set_attribute(f"{prop}_matched_count", matched_count)
    span.set_attribute(f"{prop}_evaluated_streams", total_count)

    percent_matched = (matched_count * 1.0) / (total_count * 1.0) if total_count > 0 else 1.0
    logger.info(f"{prop.capitalize()} percent matched: {percent_matched}")
    return float(percent_matched)


def primary_keys_eval(expected: dict, output: dict) -> float:
    """Evaluate if primary keys match expected values for each stream.

    Returns the percentage of streams with correct primary keys.
    """
    return _eval_expected_stream_props(
        expected_stream_props=_parse_expected_streams_dict(expected, having="primary_key"),
        output_stream_props={
            stream.get("name", "(undeclared)"): stream
            for stream in _get_manifest_streams(output) or []
        },
        prop="primary_key",
    )


def records_eval(expected: dict, output: dict) -> float:
    """Evaluate if record counts match expected values for each stream.

    Returns the percentage of streams with correct record counts.
    Supports both integer values and constraint strings like ">100", "<999", ">100,<999".
    """
    readiness_report = _get_readiness_report(output)
    if readiness_report is None:
        logger.warning("No readiness report found")
        return 0.0

    expected_streams = _parse_expected_streams_dict(expected, having="expected_records")

    matched_count = 0

    for stream_name, stream_config in expected_streams.items():
        expected_value = stream_config["expected_records"]
        actual_count = _extract_record_count(readiness_report, stream_name)

        if actual_count is None:
            logger.warning(f"✗ {stream_name}: could not extract record count from report")
            continue

        if _validate_record_count(actual_count, expected_value):
            matched_count += 1
            logger.info(
                f"✓ {stream_name}: record count {actual_count} meets expectation {expected_value}"
            )
        else:
            logger.warning(
                f"✗ {stream_name}: record count {actual_count} does not meet expectation {expected_value}"
            )

    span = get_current_span()
    span.set_attribute("matched_records_count", matched_count)
    span.set_attribute("total_evaluated_streams", len(expected_streams))

    percent_matched = matched_count / len(expected_streams) if len(expected_streams) > 0 else 1.0
    logger.info(f"Records percent matched: {percent_matched}")
    return float(percent_matched)


def _extract_record_count(readiness_report: str, stream_name: str) -> int | None:
    """Extract record count for a stream from the readiness report."""
    lines = readiness_report.split("\n")
    for i, line in enumerate(lines):
        if f"**{stream_name}**" in line or f"`{stream_name}`" in line:
            for j in range(i, min(i + 10, len(lines))):
                if "records" in lines[j].lower():
                    match = re.search(r"(\d+)\s+records?", lines[j], re.IGNORECASE)
                    if match:
                        return int(match.group(1))
    return None


def _validate_record_count(actual_count: int, expected_value: int | str) -> bool:
    """Validate record count against expected value or constraint string."""
    if isinstance(expected_value, int):
        return actual_count == expected_value

    if not isinstance(expected_value, str):
        return False

    constraints = [c.strip() for c in expected_value.split(",")]
    for constraint in constraints:
        if constraint.startswith(">"):
            threshold = int(constraint[1:])
            if actual_count <= threshold:
                return False
        elif constraint.startswith("<"):
            threshold = int(constraint[1:])
            if actual_count >= threshold:
                return False
        elif constraint.isdigit():
            if actual_count != int(constraint):
                return False

    return True
