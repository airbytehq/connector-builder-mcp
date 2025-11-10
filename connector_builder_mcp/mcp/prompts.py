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
    BUILD_CONNECTOR_FROM_SCRATCH_PROMPT,
)
from connector_builder_mcp.mcp._mcp_utils import (
    ToolDomain,
    mcp_prompt,
)
from connector_builder_mcp.mcp._mcp_utils import (
    register_prompts as register_deferred_prompts,
)


@mcp_prompt(
    name="build_connector_from_scratch",
    description="Step-by-step playbook to build a declarative connector from scratch",
)
def build_connector_from_scratch(
    api_name: Annotated[
        str | None,
        Field(description="Optional API name to build connector for"),
    ] = None,
    docs_url: Annotated[
        str | None,
        Field(description="Optional URL to API documentation"),
    ] = None,
) -> list[dict[str, str]]:
    """Prompt for building a connector from scratch.

    Args:
        api_name: Optional name of the API to build connector for
        docs_url: Optional URL to API documentation

    Returns:
        List of message dictionaries for the prompt
    """
    content = BUILD_CONNECTOR_FROM_SCRATCH_PROMPT.format(
        api_name=api_name or "the target API",
        docs_url=docs_url or "(locate API docs)",
    )
    return [{"role": "user", "content": content}]


@mcp_prompt(
    name="add_stream_to_connector",
    description="Playbook to add a new stream to an existing connector",
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
    register_deferred_prompts(app, domain=ToolDomain.GUIDANCE)
