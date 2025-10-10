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

Execute tasks in small steps, narrating your internal monologue as you go. In general,
you can break the work into small incremental steps:
1. Aim for a first successful stream read, ignoring pagination and additional streams.
2. Once you have a successful read, see if you can add pagination support to that stream.
3. Once you are able to read all records from that stream, try to add more streams incrementally,
focusing on adding and then testing one new stream at a time.

Monitor progress and ensure each step completes successfully before moving to the next.

When checking on the progress of your developer:
- Use your tools to retrieve the latest progress log and the "readiness report".
- Based on the progress log and readiness report, determine what next steps are needed.

If the build is complete, summarize the results and evaluate whether they meet the requirements. If
not, you can repeat a task, calling out what they missed and suggesting next steps. Determine the
next steps or next appropriate action based on their progress.

## Exit Criteria

- You are done when all deliverables are complete, all streams have been added, and the connector
  is fully tested and working properly. When this is the case, call the `mark_job_success` tool.
  (Only call if you are sure the build is fully complete and fully tested.)
- If you become fully blocked and cannot proceed, use your provided tool to mark the task as failed,
  providing a summary of the issues encountered. (Last resort only.)
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
            INTERNAL_MONOLOGUE_GUIDANCE,
            get_project_directory_prompt(project_directory),
            RECOMMENDED_PROMPT_PREFIX,
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
