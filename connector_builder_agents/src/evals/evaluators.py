# Copyright (c) 2025 Airbyte, Inc., all rights reserved.
"""Evaluators for connector builder agents."""

import json
import logging

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


def readiness_eval(output: dict) -> int:
    """Create Phoenix LLM classifier for readiness evaluation. Return 1 if PASSED, 0 if FAILED."""

    if output is None:
        logger.warning("Output is None, cannot evaluate readiness")
        return 0

    readiness_report = output.get("artifacts", {}).get("readiness_report", None)
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


def streams_eval(expected: dict, output: dict) -> float:
    """Evaluate if all expected streams were built. Return the percentage of expected streams that are present in available streams."""

    if output is None:
        logger.warning("Output is None, cannot evaluate streams")
        return 0.0

    manifest_str = output.get("artifacts", {}).get("manifest", None)
    if manifest_str is None:
        logger.warning("No manifest found")
        return 0

    manifest = yaml.safe_load(manifest_str)
    available_streams = manifest.get("streams", [])
    available_stream_names = [stream.get("name", "") for stream in available_streams]
    logger.info(f"Available stream names: {available_stream_names}")

    expected_obj = json.loads(expected.get("expected", "{}"))
    expected_streams = expected_obj.get("expected_streams", [])

    # expected_streams is now a list of dicts like [{"posts": {"primary_key": ["id"]}}, ...]
    expected_stream_names = []
    for stream_obj in expected_streams:
        if isinstance(stream_obj, dict):
            expected_stream_names.extend(stream_obj.keys())
        elif isinstance(stream_obj, str):
            expected_stream_names.append(stream_obj)

    logger.info(f"Expected stream names: {expected_stream_names}")

    # Set attributes on span for visibility
    span = get_current_span()
    span.set_attribute("available_stream_names", available_stream_names)
    span.set_attribute("expected_stream_names", expected_stream_names)

    if not expected_stream_names:
        logger.warning("No expected streams found")
        return 0.0

    # Calculate the percentage of expected streams that are present in available streams
    matched_streams = set(available_stream_names) & set(expected_stream_names)
    logger.info(f"Matched streams: {matched_streams}")
    percent_matched = len(matched_streams) / len(expected_stream_names)
    logger.info(f"Percent matched: {percent_matched}")
    return float(percent_matched)


def primary_keys_eval(expected: dict, output: dict) -> float:
    """Evaluate if primary keys match expected values for each stream.

    Returns the percentage of streams with correct primary keys.
    """
    if output is None:
        logger.warning("Output is None, cannot evaluate primary keys")
        return 0.0

    manifest_str = output.get("artifacts", {}).get("manifest", None)
    if manifest_str is None:
        logger.warning("No manifest found")
        return 0.0

    manifest = yaml.safe_load(manifest_str)
    available_streams = manifest.get("streams", [])

    expected_obj = json.loads(expected.get("expected", "{}"))
    expected_streams = expected_obj.get("expected_streams", [])

    # expected_streams is now a list of dicts like [{"posts": {"primary_key": ["id"]}}, ...]
    expected_primary_keys = {}
    for stream_obj in expected_streams:
        if isinstance(stream_obj, dict):
            for stream_name, stream_config in stream_obj.items():
                if isinstance(stream_config, dict) and "primary_key" in stream_config:
                    expected_primary_keys[stream_name] = stream_config["primary_key"]

    logger.info(f"Expected primary keys: {expected_primary_keys}")

    if not expected_primary_keys:
        logger.warning("No expected primary keys found")
        return 0.0

    matched_count = 0
    total_expected_streams = len(expected_primary_keys)

    for stream in available_streams:
        stream_name = stream.get("name", "")
        if stream_name not in expected_primary_keys:
            continue

        actual_pk = stream.get("primary_key", [])
        expected_pk = expected_primary_keys[stream_name]

        if actual_pk == expected_pk:
            matched_count += 1
            logger.info(f"✓ {stream_name}: primary key matches {expected_pk}")
        else:
            logger.warning(
                f"✗ {stream_name}: primary key mismatch - expected {expected_pk}, got {actual_pk}"
            )

    span = get_current_span()
    span.set_attribute("matched_primary_keys_count", matched_count)
    span.set_attribute("total_expected_streams", total_expected_streams)

    percent_matched = matched_count / total_expected_streams if total_expected_streams > 0 else 0.0
    logger.info(f"Primary keys percent matched: {percent_matched}")
    return float(percent_matched)


def records_eval(expected: dict, output: dict) -> float:
    """Evaluate if record counts match expected values for each stream.

    Returns the percentage of streams with correct record counts.
    Supports both integer values and constraint strings like ">100", "<999", ">100,<999".
    """
    if output is None:
        logger.warning("Output is None, cannot evaluate records")
        return 0.0

    readiness_report = output.get("artifacts", {}).get("readiness_report", None)
    if readiness_report is None:
        logger.warning("No readiness report found")
        return 0.0

    expected_obj = json.loads(expected.get("expected", "{}"))
    expected_streams = expected_obj.get("expected_streams", [])

    expected_records = {}
    for stream_obj in expected_streams:
        if isinstance(stream_obj, dict):
            for stream_name, stream_config in stream_obj.items():
                if isinstance(stream_config, dict) and "expected_records" in stream_config:
                    expected_records[stream_name] = stream_config["expected_records"]

    logger.info(f"Expected records: {expected_records}")

    if not expected_records:
        logger.warning("No expected records found")
        return 1.0

    matched_count = 0
    total_expected_streams = len(expected_records)

    for stream_name, expected_value in expected_records.items():
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
    span.set_attribute("total_expected_streams", total_expected_streams)

    percent_matched = matched_count / total_expected_streams if total_expected_streams > 0 else 0.0
    logger.info(f"Records percent matched: {percent_matched}")
    return float(percent_matched)


def _extract_record_count(readiness_report: str, stream_name: str) -> int | None:
    """Extract record count for a stream from the readiness report."""
    lines = readiness_report.split("\n")
    for i, line in enumerate(lines):
        if f"**{stream_name}**" in line or f"`{stream_name}`" in line:
            for j in range(i, min(i + 10, len(lines))):
                if "records" in lines[j].lower():
                    import re

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
