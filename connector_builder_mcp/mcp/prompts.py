# Copyright (c) 2025 Airbyte, Inc., all rights reserved.
"""MCP prompts for the Connector Builder MCP server.

This module provides pre-built instruction templates that guide users through
common connector building workflows.
"""

from typing import Annotated

from fastmcp import FastMCP
from pydantic import Field

from connector_builder_mcp._guidance import (
    ADD_STREAM_TO_CONNECTOR_PROMPT,
    CONNECTOR_BUILD_PROMPT,
    CREATIVE_MODE_NOTE,
    NON_CREATIVE_MODE_NOTE,
)
from connector_builder_mcp.mcp._mcp_utils import (
    ToolDomain,
    mcp_prompt,
    register_mcp_prompts,
)


@mcp_prompt(
    name="new_connector",
    description="Build a test connector to verify MCP server functionality",
    domain=ToolDomain.PROMPTS,
)
def new_connector_prompt(
    api_name: Annotated[
        str | None,
        Field(
            description="Optional API name (defaults to JSONPlaceholder)",
            default=None,
        ),
    ] = None,
    dotenv_path: Annotated[
        str | None,
        Field(
            description="Optional path to .env file for secrets",
            default=None,
        ),
    ] = None,
    additional_requirements: Annotated[
        str | None,
        Field(
            description="Optional additional requirements for the connector",
            default=None,
        ),
    ] = None,
    creative_mode: Annotated[
        bool | None,
        Field(
            description=(
                "By default, we discourage creative workarounds because those increase "
                "the agent's likelihood of making mistakes. "
                "You can enable this setting if you know what you are doing.",
            ),
            default=False,
        ),
    ] = False,
) -> list[dict[str, str]]:
    """Prompt for debugging and testing the MCP server by building a connector.

    Returns:
        List of message dictionaries for the prompt
    """
    if not api_name:
        api_name, dotenv_path = "JSONPlaceholder", "n/a"

    creative_mode = creative_mode if creative_mode is not None else False
    base_content = CONNECTOR_BUILD_PROMPT.format(
        api_name=api_name,
        dotenv_path=dotenv_path or "(none - search for API docs to determine if needed)",
        additional_requirements=additional_requirements or "(none)",
    )
    content = base_content + (CREATIVE_MODE_NOTE if creative_mode else NON_CREATIVE_MODE_NOTE)
    return [{"role": "user", "content": content}]


@mcp_prompt(
    name="add_stream_to_connector",
    description="Playbook to add a new stream to an existing connector",
    domain=ToolDomain.PROMPTS,
)
def add_stream_to_connector(
    stream_name: Annotated[
        str | None,
        Field(description="Name of the stream to add"),
    ] = None,
    manifest_path: Annotated[
        str | None,
        Field(description="Path to existing manifest.yaml file"),
    ] = None,
) -> list[dict[str, str]]:
    """Prompt for adding a new stream to an existing connector.

    Args:
        stream_name: Name of the stream to add
        manifest_path: Path to existing manifest file

    Returns:
        List of message dictionaries for the prompt
    """
    content = ADD_STREAM_TO_CONNECTOR_PROMPT.format(
        stream_name=stream_name or "a new stream",
        manifest_path=manifest_path or "(path to manifest)",
    )
    return [{"role": "user", "content": content}]


def register_prompts(app: FastMCP) -> None:
    """Register connector builder prompts with the FastMCP app.

    Args:
        app: FastMCP application instance
    """
    register_mcp_prompts(app, domain=ToolDomain.PROMPTS)
