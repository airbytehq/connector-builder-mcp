# Copyright (c) 2025 Airbyte, Inc., all rights reserved.

import json
import logging
import time

from opentelemetry import trace

from connector_builder_agents.src.evals.helpers import ConnectorBuilderEvalTaskOutput

from ..constants import DEFAULT_DEVELOPER_MODEL, DEFAULT_MANAGER_MODEL
from ..run import TokenUsage, get_workspace_dir, run_connector_build
from .helpers import create_connector_builder_eval_task_output, get_artifact


logger = logging.getLogger(__name__)

EVAL_DEVELOPER_MODEL = DEFAULT_DEVELOPER_MODEL
EVAL_MANAGER_MODEL = DEFAULT_MANAGER_MODEL


tracer = trace.get_tracer("connector_build_task")


async def run_connector_build_task(dataset_row: dict) -> ConnectorBuilderEvalTaskOutput:
    input_obj = json.loads(dataset_row.get("input", "{}"))
    connector_name = input_obj.get("name", "unknown")
    prompt_name = input_obj.get("prompt_name", "unknown")
    session_id = f"eval-{connector_name}-{int(time.time())}"

    logger.info(
        f"Starting connector build task for '{connector_name}' with prompt '{prompt_name}' (session: {session_id})"
    )

    current_span = trace.get_current_span()

    current_span.set_attribute("experiment.session_id", session_id)
    current_span.set_attribute("experiment.connector_name", connector_name)
    current_span.set_attribute("experiment.prompt_name", prompt_name)

    token_usage = TokenUsage()

    try:
        build_result = await run_connector_build(
            api_name=prompt_name,
            session_id=session_id,
            developer_model=EVAL_DEVELOPER_MODEL,
            manager_model=EVAL_MANAGER_MODEL,
            token_usage=token_usage,
        )
    except Exception as e:
        logger.error(f"Failed to build connector '{connector_name}': {e}")
        raise

    current_span.set_attribute("llm.token_count.prompt", token_usage.total_input_tokens)
    current_span.set_attribute("llm.token_count.completion", token_usage.total_output_tokens)
    current_span.set_attribute("llm.token_count.total", token_usage.total_tokens)
    current_span.set_attribute("llm.model_name", EVAL_MANAGER_MODEL)
    current_span.set_attribute("llm.provider", "openai")

    workspace_dir = get_workspace_dir(session_id)
    logger.info(f"Workspace directory: {workspace_dir}")

    final_result = build_result[-1] if build_result else None
    success = build_result is not None
    num_turns = len(build_result) if build_result else 0

    logger.info(f"Build completed - Success: {success}, Turns: {num_turns}")

    # Read artifacts
    readiness_report_content = get_artifact(workspace_dir, "connector-readiness-report.md", logger)
    manifest_content = get_artifact(workspace_dir, "manifest.yaml", logger)

    logger.info(f"Task completed successfully for connector '{connector_name}'")

    connector_builder_eval_task_output = create_connector_builder_eval_task_output(
        {
            "workspace_dir": workspace_dir.absolute(),
            "success": success,
            "final_output": final_result.output if final_result else None,
            "num_turns": num_turns,
            "artifacts": {
                "readiness_report": readiness_report_content,
                "manifest": manifest_content,
            },
        }
    )

    return connector_builder_eval_task_output
