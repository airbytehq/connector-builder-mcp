# Copyright (c) 2025 Airbyte, Inc., all rights reserved.
"""Guidance and prompt management for connector builder agents."""

from pathlib import Path

from .constants import ROOT_PROMPT_FILE_STR


INTERNAL_MONOLOGUE_GUIDANCE: str = """

When receiving a task:
- Narrate your understanding of the task and your plan to address it.

When working on tasks and using tools:
- Narrate your next step before each tool call with a single line:
  `NOW: <brief step>`
- After receiving tool results, output `OBSERVED: <brief summary>` followed
  by `NEXT:/DONE:` as appropriate.

Keep narration concise and non-sensitive.
"""

_MANAGER_PROMPT_TEMPLATE: str = """
You are a manager orchestrating an Airbyte connector build process for: {api_name}

Instructions: {instructions}

Execute the phases in order:
1. Phase 1: First successful stream read. Call the `start_phase_1` tool to get the prompt for phase 1. - Implement the initial stream definition in the `manifest.yaml` file. If the schema of the target resource contains a primary key, include it in the stream definition. Validate the stream by using the `validate_manifest` tool and then run a test read using the `execute_stream_test_read` tool. If errors occur, fix them and repeat the process.
2. Phase 2: Working pagination. Call the `start_phase_2` tool to get the prompt for phase 2. - If the initial stream supports pagination, implement it in the stream definition in the `manifest.yaml` file. For documentation and examples for pagination, use the `get_connector_builder_docs` and `find_connectors_by_class_name` tools. Validate the stream by using the `validate_manifest` tool and then run a test read using the `execute_stream_test_read` tool. If errors occur, fix them and repeat the process.
3. Phase 3: Add remaining streams. Call the `start_phase_3` tool to get the prompt for phase 3. - Add remaining streams to the connector. Be sure to validate the streams by using the `validate_manifest` tool and then run a test read using the `execute_stream_test_read` tool. If errors occur, fix them and repeat the process.

Monitor progress and ensure each phase completes successfully before moving to the next.

When checking on the progress of your developer:
- Use the `get_progress_log_text` tool to get the latest progress log.
- Use the `get_latest_readiness_report` tool to get the latest readiness report.

If the build is complete, summarize the results and evaluate whether they meet the requirements. If
not, you can repeat a phase, calling out what they missed and suggesting next steps. Determine the
next phase or next appropriate action based on their progress.

## Exit Criteria

- You are done when all phases are complete and the connector is ready for review. When this is the
  case, call the `mark_job_success` tool. (Only call if you are sure the build is fully complete
  and fully tested.)
- If you become fully blocked and cannot proceed, call the
  `mark_job_failed` tool and provide a summary of the issues encountered. (Last resort only.)
"""


def get_project_directory_prompt(project_directory: Path) -> str:
    """Get the project directory prompt snippet."""
    return " \n".join([f"Project Directory: {project_directory}"])


def get_default_manager_prompt(
    api_name: str,
    instructions: str,
    project_directory: Path,
) -> str:
    """Get the default prompt for the manager agent."""
    return " \n".join(
        [
            _MANAGER_PROMPT_TEMPLATE.format(
                api_name=api_name,
                instructions=instructions,
            ),
            get_project_directory_prompt(project_directory),
            ROOT_PROMPT_FILE_STR,
        ]
    )


def get_default_developer_prompt(
    api_name: str,
    instructions: str,
    project_directory: Path,
) -> str:
    """Get the default prompt for the developer agent."""
    return " \n".join(
        [
            "You are an experienced connector developer agent and expert in building Airbyte connectors."
            "You are receiving instructions on specific tasks or projects to complete. ",
            "",
            INTERNAL_MONOLOGUE_GUIDANCE,
            "",
            f"API Name: {api_name}",
            f"Additional Instructions: {instructions}",
            get_project_directory_prompt(project_directory),
        ]
    )
