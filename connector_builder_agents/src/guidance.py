# Copyright (c) 2025 Airbyte, Inc., all rights reserved.
"""Guidance and prompt management for connector builder agents."""

from pathlib import Path

from agents.extensions.handoff_prompt import RECOMMENDED_PROMPT_PREFIX

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
1. Use start_phase_1_stream_read to delegate Phase 1 (first successful stream read)
2. After Phase 1 completes, use start_phase_2_pagination to delegate Phase 2 (working pagination)
3. After Phase 2 completes, use start_phase_3_remaining_streams to delegate Phase 3 (add remaining streams)

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
  `mark_job_failed` tool, providing a summary of the issues encountered. (Last resort only.)
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
    return " \n".join([
        _MANAGER_PROMPT_TEMPLATE.format(
            api_name=api_name,
            instructions=instructions,
        ),
        get_project_directory_prompt(project_directory),
        RECOMMENDED_PROMPT_PREFIX,
        ROOT_PROMPT_FILE_STR,
    ])


def get_default_developer_prompt(
    api_name: str,
    instructions: str,
    project_directory: Path,
) -> str:
    """Get the default prompt for the developer agent."""
    return " \n".join([
        "You are an experienced connector developer agent and expert in building Airbyte connectors."
        "You are receiving instructions on specific tasks or projects to complete. ",
        "",
        INTERNAL_MONOLOGUE_GUIDANCE,
        "",
        f"API Name: {api_name}",
        f"Additional Instructions: {instructions}",
        get_project_directory_prompt(project_directory),
    ])
