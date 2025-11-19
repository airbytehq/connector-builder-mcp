# Copyright (c) 2025 Airbyte, Inc., all rights reserved.
"""MCP prompts for OpenAPI/Sonar connector building.

This module provides pre-built instruction templates that guide users through
building OpenAPI-based connectors.
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
    name="new_openapi_connector",
    description="Build a connector from an OpenAPI specification",
    domain=ToolDomain.PROMPTS,
)
def new_openapi_connector_prompt(
    api_name: Annotated[
        str | None,
        Field(
            description="Optional API name",
            default=None,
        ),
    ] = None,
    openapi_spec_path: Annotated[
        str | None,
        Field(
            description="Optional path to OpenAPI specification file",
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
    """Prompt for building a connector from an OpenAPI specification.

    Returns:
        List of message dictionaries for the prompt
    """
    api_name = api_name or "Example API"
    openapi_spec_path = openapi_spec_path or "(path to OpenAPI spec)"
    additional_requirements = additional_requirements or "(none)"

    content = f"""# Build OpenAPI/Sonar Connector

Build an Airbyte connector for **{api_name}** using an OpenAPI specification and Sonar's connector-sdk.


- **API Name**: {api_name}
- **OpenAPI Spec**: {openapi_spec_path}
- **Additional Requirements**: {additional_requirements}


1. **Get the checklist**: Start by calling `get_connector_builder_checklist()` to see the full development workflow
2. **Locate OpenAPI spec**: Find or obtain the OpenAPI 3.0 specification (YAML or JSON)
3. **Validate spec**: Use `validate_openapi_spec()` to check the specification
4. **Enumerate resources**: Identify all available API resources/endpoints
5. **Configure authentication**: Set up security schemes from the OpenAPI spec
6. **Add x-airbyte extensions**: Mark resources and configure behavior
7. **Test each resource**: Validate that each resource works correctly
8. **Run readiness check**: Ensure all resources pass validation


- Use x-airbyte-resource to mark operations as Airbyte resources
- Configure pagination with x-airbyte-pagination
- Map OpenAPI schemas to Airbyte schemas automatically
- Test incrementally as you add each resource


Call `get_openapi_connector_docs()` for detailed guidance on:
- x-airbyte extensions
- Authentication patterns
- Pagination strategies
- Schema mapping

Begin by getting the checklist and understanding the workflow.
"""

    return [{"role": "user", "content": content}]


def register_prompts(app: FastMCP) -> None:
    """Register OpenAPI/Sonar connector builder prompts with the FastMCP app.

    Args:
        app: FastMCP application instance
    """
    register_mcp_prompts(app, domain=ToolDomain.PROMPTS)
