# Copyright (c) 2025 Airbyte, Inc., all rights reserved.
"""Evaluators for connector builder agents."""

import json
import logging

import pandas as pd
import yaml
from dotenv import load_dotenv
from opentelemetry.trace import get_current_span
from phoenix.evals import OpenAIModel, llm_classify

from airbyte_cdk.sources.declarative.models import DeclarativeSource
from connector_builder_agents.src.evals.task import ConnectorBuilderEvalTaskOutput


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


def manifest_validation_eval(output: dict | None) -> int:
    """Evaluate if the manifest is valid by parsing it as a DeclarativeSource. Return 1 if PASSED, 0 if FAILED."""

    if output is None:
        logger.warning("No output provided - build task likely failed")
        return 0

    connector_builder_eval_task_output = ConnectorBuilderEvalTaskOutput(**output)

    manifest = connector_builder_eval_task_output.artifacts.get("manifest", None)
    if manifest is None:
        logger.warning("No manifest found")
        return 0

    try:
        manifest_dict = yaml.safe_load(manifest)
    except yaml.YAMLError as e:
        logger.warning(f"Failed to parse manifest YAML: {e}")
        return 0

    try:
        DeclarativeSource.parse_obj(manifest_dict)
    except Exception as e:
        logger.warning(f"Failed to parse DeclarativeSource from manifest: {e}")
        return 0

    return 1


def readiness_eval(output: dict | None) -> float:
    """Create Phoenix LLM classifier for readiness evaluation. Return 1 if PASSED, 0 if FAILED."""

    if output is None:
        logger.warning("No output provided - build task likely failed")
        return 0.0

    connector_builder_eval_task_output = ConnectorBuilderEvalTaskOutput(**output)

    readiness_report = connector_builder_eval_task_output.artifacts.get("readiness_report", None)
    if readiness_report is None:
        logger.warning("No readiness report found")
        return 0.0

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
    score = 1.0 if label.upper() == "PASSED" else 0.0

    return score


def streams_eval(expected: dict, output: dict | None) -> float:
    """Evaluate if all expected streams were built. Return the percentage of expected streams that are present in available streams."""

    if output is None:
        logger.warning("No output provided - build task likely failed")
        return 0.0

    connector_builder_eval_task_output = ConnectorBuilderEvalTaskOutput(**output)

    manifest_str = connector_builder_eval_task_output.artifacts.get("manifest", None)
    if not manifest_str:
        logger.warning("No manifest found or manifest is empty")
        return 0.0

    try:
        manifest_dict = yaml.safe_load(manifest_str)
    except yaml.YAMLError as e:
        logger.warning(f"Failed to parse manifest YAML: {e}")
        return 0.0

    try:
        declarative_source = DeclarativeSource.parse_obj(manifest_dict)
        if hasattr(declarative_source, "__root__"):
            declarative_source = declarative_source.__root__
    except Exception as e:
        logger.error(f"Failed to parse DeclarativeSource from manifest: {e}")
        return 0.0

    available_stream_names = []
    for stream in declarative_source.streams:
        available_stream_names.append(stream.name)
    logger.info(f"Available stream names: {available_stream_names}")

    expected_obj = json.loads(expected.get("expected", "{}"))
    expected_streams = expected_obj.get("expected_streams", [])
    expected_stream_names = [stream["name"] for stream in expected_streams]

    # Set attributes on span for visibility
    span = get_current_span()
    span.set_attribute("available_stream_names", available_stream_names)
    span.set_attribute("expected_stream_names", expected_stream_names)

    if not expected_stream_names:
        logger.warning("No expected streams found")
        return 0.0

    matched_streams = set(available_stream_names) & set(expected_stream_names)
    logger.info(f"Matched streams: {matched_streams}")
    percent_matched = len(matched_streams) / len(expected_stream_names)
    logger.info(f"Percent matched: {percent_matched}")
    return float(percent_matched)


def primary_key_eval(expected: dict, output: dict | None) -> float:
    """Evaluate if the primary keys of the matched expected streams match the expected primary keys."""

    if not output:
        logger.warning("No output provided - build task likely failed")
        return 0.0

    manifest_str = ConnectorBuilderEvalTaskOutput(**output).artifacts.get("manifest")
    if not manifest_str:
        logger.warning("No manifest found or manifest is empty")
        return 0.0

    try:
        manifest = yaml.safe_load(manifest_str)
        declarative_source = DeclarativeSource.parse_obj(manifest)
        declarative_source = getattr(declarative_source, "__root__", declarative_source)
    except Exception as e:
        logger.error(f"Failed to parse DeclarativeSource from manifest: {e}")
        return 0.0

    expected_streams = json.loads(expected.get("expected", "{}")).get("expected_streams", [])
    if not expected_streams:
        logger.warning("No expected streams found")
        return 0.0

    expected_by_name = {stream["name"]: stream.get("primary_key") for stream in expected_streams}
    available = {s.name: s for s in declarative_source.streams}
    matched_names = set(expected_by_name) & set(available)

    if not matched_names:
        logger.info("No matching streams found")
        return 0.0

    correct = 0
    for name in matched_names:
        pk = getattr(available[name], "primary_key", None)
        actual_pk = getattr(pk, "__root__", pk)
        if actual_pk == expected_by_name[name]:
            correct += 1

    return correct / len(matched_names)


EVALUATORS = [manifest_validation_eval, readiness_eval, streams_eval, primary_key_eval]
