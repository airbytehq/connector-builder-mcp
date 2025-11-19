# Copyright (c) 2025 Airbyte, Inc., all rights reserved.
"""MCP prompts for Kotlin source connector building.

This module provides pre-built instruction templates that guide users through
building Kotlin-based source connectors.
"""

from typing import Annotated

from fastmcp import FastMCP
from pydantic import Field

from connector_builder_mcp.mcp._mcp_utils import (
    ToolDomain,
    mcp_prompt,
    register_mcp_prompts,
)


@mcp_prompt(
    name="new_kotlin_source_connector",
    description="Build a Kotlin-based source connector",
    domain=ToolDomain.PROMPTS,
)
def new_kotlin_source_connector_prompt(
    api_name: Annotated[
        str | None,
        Field(
            description="Optional API name",
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
) -> list[dict[str, str]]:
    """Prompt for building a Kotlin-based source connector.

    Returns:
        List of message dictionaries for the prompt
    """
    api_name = api_name or "Example API"
    additional_requirements = additional_requirements or "(none)"

    content = f"""# Build Kotlin Source Connector

Build an Airbyte source connector for **{api_name}** using Kotlin.


- **API Name**: {api_name}
- **Additional Requirements**: {additional_requirements}


1. **Get the checklist**: Start by calling `get_connector_builder_checklist()` to see the full development workflow
2. **Setup environment**: Ensure JDK, Gradle, and Kotlin are properly configured
3. **Locate API docs**: Find comprehensive API documentation
4. **Enumerate streams**: Identify all available data streams/endpoints
5. **Identify authentication**: Determine auth method (API key, OAuth, etc.)
6. **Create scaffold**: Generate project structure with build files
7. **Implement spec**: Define configuration parameters
8. **Implement check**: Validate connection and credentials
9. **Implement streams**: Create stream classes for each data source
10. **Test incrementally**: Test each stream as you implement it
11. **Run readiness check**: Ensure all streams pass validation
12. **Build and package**: Create Docker image


- Extend HttpStream for REST API sources
- Implement IncrementalStream for incremental sync support
- Override path(), parseResponse(), nextPageToken() methods
- Handle authentication with appropriate authenticator classes
- Implement proper error handling and retry logic


Call `get_kotlin_source_connector_docs()` for detailed guidance on:
- Stream implementation patterns
- Authentication strategies
- Pagination handling
- Incremental sync implementation
- Error handling best practices

Begin by getting the checklist and understanding the workflow.
"""

    return [{"role": "user", "content": content}]


def register_prompts(app: FastMCP) -> None:
    """Register Kotlin source connector builder prompts with the FastMCP app.

    Args:
        app: FastMCP application instance
    """
    register_mcp_prompts(app, domain=ToolDomain.PROMPTS)
