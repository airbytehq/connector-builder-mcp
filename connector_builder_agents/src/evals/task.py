# Copyright (c) 2025 Airbyte, Inc., all rights reserved.

import json
import logging
import time

from ..constants import DEFAULT_DEVELOPER_MODEL, DEFAULT_MANAGER_MODEL
from ..run import get_workspace_dir, run_connector_build
from .helpers import get_artifact


logger = logging.getLogger(__name__)

EVAL_DEVELOPER_MODEL = DEFAULT_DEVELOPER_MODEL
EVAL_MANAGER_MODEL = DEFAULT_MANAGER_MODEL


async def run_connector_build_task(dataset_row: dict) -> dict:
    input_obj = json.loads(dataset_row.get("input", "{}"))
    connector_name = input_obj.get("name", "unknown")
    prompt_name = input_obj.get("prompt_name", "unknown")
    session_id = f"eval_{connector_name.replace('-', '_')}_{int(time.time())}"

    logger.info(
        f"Starting connector build task for '{connector_name}' with prompt '{prompt_name}' (session: {session_id})"
    )

    try:
        build_result = await run_connector_build(
            api_name=prompt_name,
            session_id=session_id,
            developer_model=EVAL_DEVELOPER_MODEL,
            manager_model=EVAL_MANAGER_MODEL,
        )

        workspace_dir = get_workspace_dir(session_id)
        logger.info(f"Workspace directory: {workspace_dir}")

        final_result = build_result[-1] if build_result else None
        success = build_result is not None
        num_turns = len(build_result) if build_result else 0

        logger.info(f"Build completed - Success: {success}, Turns: {num_turns}")

        # Read artifacts
        readiness_report_content = get_artifact(
            workspace_dir, "connector-readiness-report.md", logger
        )
        manifest_content = get_artifact(workspace_dir, "manifest.yaml", logger)

        result = {
            "workspace_dir": str(workspace_dir.absolute()),
            "success": success,
            "final_output": final_result.final_output if final_result else None,
            "num_turns": num_turns,
            "artifacts": {
                "readiness_report": readiness_report_content,
                "manifest": manifest_content,
            },
        }

        logger.info(f"Task completed successfully for connector '{connector_name}'")
        return result

    except Exception as e:
        logger.error(f"Failed to build connector '{connector_name}': {e}")
        raise
