# Copyright (c) 2024 Airbyte, Inc., all rights reserved.
"""MCP smoke test prompt for validating all tools and resources."""

from typing import Annotated

from fastmcp import FastMCP
from pydantic import Field

from connector_builder_mcp.mcp._mcp_utils import (
    _REGISTERED_PROMPTS,
    _REGISTERED_RESOURCES,
    _REGISTERED_TOOLS,
    ToolDomain,
    mcp_prompt,
    register_mcp_prompts,
)


@mcp_prompt(
    name="mcp_smoke_tests_prompt",
    description="Run smoke tests on all MCP tools and resources to confirm they are working properly",
    domain=ToolDomain.PROMPTS,
)
def mcp_smoke_tests_prompt(
    read_only: Annotated[
        bool,
        Field(
            description="If True, only test read-only tools. If False, test all tools including destructive ones.",
            default=True,
        ),
    ],
) -> list[dict[str, str]]:
    """Run smoke tests on all MCP tools and resources to confirm they are working properly.

    This prompt provides instructions for testing all available MCP tools and checking
    all MCP resource assets.
    """
    all_tools = _REGISTERED_TOOLS

    if read_only:
        tools_to_test = [(func, ann) for func, ann in all_tools if ann.get("readOnlyHint", False)]
    else:
        tools_to_test = all_tools

    tools_by_domain: dict[str, list[str]] = {}
    for func, ann in tools_to_test:
        domain = ann.get("domain", "unknown")
        if domain not in tools_by_domain:
            tools_by_domain[domain] = []
        tools_by_domain[domain].append(func.__name__)

    all_resources = _REGISTERED_RESOURCES
    resources_by_domain: dict[str, list[str]] = {}
    for func, ann in all_resources:
        domain = ann.get("domain", "unknown")
        if domain not in resources_by_domain:
            resources_by_domain[domain] = []
        uri = ann.get("uri", func.__name__)
        resources_by_domain[domain].append(uri)

    all_prompts = _REGISTERED_PROMPTS
    prompt_names = [ann.get("name", func.__name__) for func, ann in all_prompts]

    prompt_parts = [
        "# MCP Smoke Test Instructions\n",
        f"Testing mode: {'READ-ONLY' if read_only else 'ALL TOOLS (including destructive)'}\n",
        "\n## Overview\n",
        "This smoke test will validate that all MCP tools, prompts, and resources are functioning correctly. ",
        "Follow the instructions below to test each component systematically.\n",
        "\n## Tools to Test\n",
    ]

    for domain, tool_names in sorted(tools_by_domain.items()):
        prompt_parts.append(f"\n### Domain: {domain}\n")
        prompt_parts.append(f"Number of tools: {len(tool_names)}\n")
        prompt_parts.append("Tools:\n")
        for tool_name in sorted(tool_names):
            prompt_parts.append(f"- {tool_name}\n")

    prompt_parts.append("\n## Resources to Test\n")
    for domain, resource_uris in sorted(resources_by_domain.items()):
        prompt_parts.append(f"\n### Domain: {domain}\n")
        prompt_parts.append(f"Number of resources: {len(resource_uris)}\n")
        prompt_parts.append("Resources:\n")
        for uri in sorted(resource_uris):
            prompt_parts.append(f"- {uri}\n")

    prompt_parts.append("\n## Prompts Available\n")
    prompt_parts.append(f"Number of prompts: {len(prompt_names)}\n")
    prompt_parts.append("Prompts:\n")
    for prompt_name in sorted(prompt_names):
        prompt_parts.append(f"- {prompt_name}\n")

    prompt_parts.extend(
        [
            "\n## Testing Instructions\n",
            "\n### 1. Tool Testing\n",
            "For each tool listed above:\n",
            "1. Call the tool with minimal/safe parameters\n",
            "2. Verify it returns a response without errors\n",
            "3. Document any failures with error messages\n",
            "\n### 2. Resource Testing\n",
            "For each resource listed above:\n",
            "1. Attempt to read the resource using its URI\n",
            "2. Verify the content is accessible\n",
            "3. Document any failures with error messages\n",
            "\n### 3. Prompt Testing\n",
            "For each prompt listed above:\n",
            "1. Verify the prompt is accessible\n",
            "2. Check that it returns valid prompt content\n",
            "\n### 4. Report Generation\n",
            "After testing, generate a report with:\n",
            "- Total tools tested\n",
            "- Number of successful tests\n",
            "- Number of failed tests\n",
            "- List of any failures with error details\n",
            "- Resource access results\n",
            "- Prompt availability results\n",
            "\n## Expected Behavior\n",
            "- Read-only tools should execute without modifying any data\n",
            "- Tools requiring configuration should fail gracefully with clear error messages\n",
            "- All resources should be accessible\n",
            "- All prompts should be callable\n",
            "\n## Notes\n",
            "- Some tools may require valid configurations or credentials to fully test\n",
            "- Failures due to missing configuration are expected and should be documented\n",
            "- Focus on verifying that tools are callable and return appropriate responses\n",
        ]
    )

    prompt_text = "".join(prompt_parts)

    return [
        {
            "role": "user",
            "content": prompt_text,
        }
    ]


def register_smoke_test_prompt(app: FastMCP) -> None:
    """Register the smoke test prompt with the FastMCP app."""
    register_mcp_prompts(app, domain=ToolDomain.PROMPTS)
