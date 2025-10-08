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

    manifest_str = output.get("artifacts", {}).get("manifest", None)
    if manifest_str is None:
        logger.warning("No manifest found")
        return 0

    manifest = yaml.safe_load(manifest_str)
    available_streams = manifest.get("streams", [])
    available_stream_names = [stream.get("name", "") for stream in available_streams]
    logger.info(f"Available stream names: {available_stream_names}")

    expected_obj = json.loads(expected.get("expected", "{}"))
    expected_stream_names = expected_obj.get("expected_streams", [])
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
