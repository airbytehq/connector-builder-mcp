# Copyright (c) 2025 Airbyte, Inc., all rights reserved.
"""MCP prompts for Kotlin destination connector building.

This module provides pre-built instruction templates that guide users through
building Kotlin-based destination connectors.
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
    name="new_kotlin_destination_connector",
    description="Build a Kotlin-based destination connector",
    domain=ToolDomain.PROMPTS,
)
def new_kotlin_destination_connector_prompt(
    destination_name: Annotated[
        str | None,
        Field(
            description="Optional destination system name",
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
    """Prompt for building a Kotlin-based destination connector.

    Returns:
        List of message dictionaries for the prompt
    """
    destination_name = destination_name or "Example Destination"
    additional_requirements = additional_requirements or "(none)"

    content = f"""# Build Kotlin Destination Connector

Build an Airbyte destination connector for **{destination_name}** using Kotlin.


- **Destination Name**: {destination_name}
- **Additional Requirements**: {additional_requirements}


1. **Get the checklist**: Start by calling `get_connector_builder_checklist()` to see the full development workflow
2. **Setup environment**: Ensure JDK, Gradle, and Kotlin are properly configured
3. **Identify requirements**: Determine destination system requirements and supported write modes
4. **Enumerate streams**: Identify all stream types the destination will support
5. **Identify authentication**: Determine auth method for the destination system
6. **Create scaffold**: Generate project structure with build files
7. **Implement spec**: Define configuration parameters
8. **Implement check**: Validate connection and credentials
9. **Implement consumer**: Create consumer class for processing records
10. **Implement write modes**: Support append, overwrite, and/or upsert
11. **Test incrementally**: Test each stream type as you implement it
12. **Run readiness check**: Ensure all streams pass validation
13. **Build and package**: Create Docker image


- Implement AirbyteMessageConsumer for processing records
- Support multiple write modes (append, overwrite, upsert)
- Implement batching for efficient writes
- Map Airbyte types to destination system types
- Handle transactions and error recovery


Call `get_kotlin_destination_connector_docs()` for detailed guidance on:
- Consumer implementation patterns
- Write mode strategies
- Batching approaches
- Schema mapping and type conversion
- Error handling and retry logic

Begin by getting the checklist and understanding the workflow.
"""

    return [{"role": "user", "content": content}]


def register_prompts(app: FastMCP) -> None:
    """Register Kotlin destination connector builder prompts with the FastMCP app.

    Args:
        app: FastMCP application instance
    """
    register_mcp_prompts(app, domain=ToolDomain.PROMPTS)
