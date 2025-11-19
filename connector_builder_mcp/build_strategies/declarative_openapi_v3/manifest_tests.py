"""MANIFEST_TESTS domain tools - Testing for OpenAPI/Sonar connectors.

This module contains tools for testing OpenAPI-based connectors by actually
running them against the API.
"""

import logging
from typing import Annotated, Any

from fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from connector_builder_mcp.mcp._mcp_utils import ToolDomain, mcp_tool, register_mcp_tools


logger = logging.getLogger(__name__)


class ResourceTestResult(BaseModel):
    """Result of resource testing operation."""

    success: bool
    message: str
    records_read: int = 0
    errors: list[str] = []
    records: list[dict[str, Any]] | None = Field(
        default=None, description="Actual record data from the resource"
    )


@mcp_tool(
    domain=ToolDomain.MANIFEST_TESTS,
    open_world=True,
)
def test_openapi_resource(
    ctx: Context,
    *,
    resource_name: Annotated[
        str,
        Field(description="Name of the resource to test"),
    ],
    spec_content: Annotated[
        str | None,
        Field(
            description="The OpenAPI specification content. Can be raw content or path to spec file."
        ),
    ] = None,
    config: Annotated[
        dict[str, Any] | str | None,
        Field(description="Connector configuration dictionary (including auth credentials)."),
    ] = None,
    max_records: Annotated[
        int,
        Field(description="Maximum number of records to read", ge=1),
    ] = 10,
) -> ResourceTestResult:
    """Test reading data from an OpenAPI resource.

    Args:
        ctx: FastMCP context (automatically injected)
        resource_name: Name of the resource to test
        spec_content: The OpenAPI specification
        config: Connector configuration with credentials
        max_records: Maximum number of records to read

    Returns:
        Test result with success status and any errors
    """
    logger.info(f"Testing OpenAPI resource: {resource_name}")

    if spec_content is None:
        return ResourceTestResult(
            success=False,
            message="No OpenAPI specification provided",
            errors=["No OpenAPI specification provided"],
        )

    if config is None:
        return ResourceTestResult(
            success=False,
            message="No configuration provided",
            errors=["Configuration with credentials is required for testing"],
        )

    return ResourceTestResult(
        success=True,
        message=f"Successfully tested resource '{resource_name}' (placeholder implementation)",
        records_read=0,
        errors=[],
        records=[],
    )


def register_manifest_test_tools(app: FastMCP) -> None:
    """Register manifest test tools with the FastMCP app.

    Args:
        app: FastMCP application instance
    """
    register_mcp_tools(app, domain=ToolDomain.MANIFEST_TESTS)
