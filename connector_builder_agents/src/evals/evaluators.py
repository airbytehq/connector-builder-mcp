# Copyright (c) 2025 Airbyte, Inc., all rights reserved.
"""Evaluators for connector builder agents."""

import ast

import pandas as pd
import yaml
from dotenv import load_dotenv
from phoenix.evals import OpenAIModel, llm_classify


load_dotenv()

READINESS_EVAL_MODEL = OpenAIModel(model="gpt-4o")
READINESS_EVAL_TEMPLATE = """You are evaluating whether a connector readiness test passed or failed.

A passing report should have:
- All streams tested successfully (marked with ✅)
- No critical errors or failures
- Records extracted from streams (even if with warnings)
- Successful completion indicated

A failing report would have:
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
        print("No readiness report found")
        return 0

    rails = ["PASSED", "FAILED"]

    eval_df = llm_classify(
        model=READINESS_EVAL_MODEL,
        data=pd.DataFrame([{"readiness_report": readiness_report}]),
        template=READINESS_EVAL_TEMPLATE,
        rails=rails,
        provide_explanation=True,
    )

    print(eval_df)

    label = eval_df["label"][0]
    score = 1 if label.upper() == "PASSED" else 0

    return score


def streams_eval(input: dict, output: dict) -> float:
    """Evaluate if all expected streams were built. Return the percentage of expected streams that are present in available streams."""

    manifest_str = output.get("artifacts", {}).get("manifest", None)
    if manifest_str is None:
        print("No manifest found")
        return 0

    manifest = yaml.safe_load(manifest_str)
    print(f"Manifest: {manifest}")
    available_streams = manifest.get("streams", [])
    available_stream_names = [stream.get("name", "") for stream in available_streams]
    print(f"Available stream names: {available_stream_names}")

    # Get expected streams from the input (dataset row)
    expected_stream_names = ast.literal_eval(input.get("expected_streams", []))
    print(f"Expected stream names: {expected_stream_names}")

    if not expected_stream_names:
        print("No expected streams found")
        return 0.0

    # Calculate the percentage of expected streams that are present in available streams
    matched_streams = set(available_stream_names) & set(expected_stream_names)
    print(f"Matched streams: {matched_streams}")
    percent_matched = len(matched_streams) / len(expected_stream_names)
    print(f"Percent matched: {percent_matched}")
    return float(percent_matched)
