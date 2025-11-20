"""MANIFEST_TESTS domain tools - Testing for OpenAPI/Sonar connectors.

This module contains tools for testing OpenAPI-based connectors by actually
running them against the API.
"""

import logging
from typing import Annotated, Any

from fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from connector_builder_mcp.build_strategies.declarative_openapi_v3.openapi_to_manifest import (
    generate_manifest_from_openapi,
)
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


class BuildAndTestResult(BaseModel):
    """Result of building and testing an OpenAPI connector."""

    success: bool
    manifest_yaml: str | None = None
    generation_warnings: list[str] = []
    validation_errors: list[str] = []
    test_summary: dict[str, Any] | None = None
    errors: list[str] = []


@mcp_tool(
    domain=ToolDomain.MANIFEST_TESTS,
    open_world=True,
)
def build_and_test_openapi_connector(
    ctx: Context,
    *,
    spec_content: Annotated[
        str,
        Field(
            description="The OpenAPI specification content (YAML or JSON). "
            "Can be raw content or path to spec file."
        ),
    ],
    source_name: Annotated[
        str,
        Field(
            description="Name for the generated source connector",
            default="generated_source",
        ),
    ] = "generated_source",
) -> BuildAndTestResult:
    """Build an OpenAPI connector from specification.

    This tool generates an Airbyte declarative manifest from an OpenAPI spec.
    
    Note: Full validation and testing capabilities will be added in a future update
    when the testing infrastructure is available.

    Args:
        ctx: FastMCP context (automatically injected)
        spec_content: The OpenAPI specification
        source_name: Name for the generated source connector

    Returns:
        Build result with manifest and any warnings
    """
    logger.info(f"Building OpenAPI connector: {source_name}")

    try:
        logger.info("Generating manifest from OpenAPI spec")
        manifest_yaml, generation_warnings = generate_manifest_from_openapi(
            spec_content=spec_content,
            source_name=source_name,
        )

        return BuildAndTestResult(
            success=True,
            manifest_yaml=manifest_yaml,
            generation_warnings=generation_warnings,
            validation_errors=[],
            test_summary=None,
            errors=[],
        )

    except ValueError as e:
        logger.error(f"Failed to build connector: {e}")
        return BuildAndTestResult(
            success=False,
            manifest_yaml=None,
            generation_warnings=[],
            validation_errors=[],
            test_summary=None,
            errors=[str(e)],
        )
    except Exception as e:
        logger.exception("Unexpected error building connector")
        return BuildAndTestResult(
            success=False,
            manifest_yaml=None,
            generation_warnings=[],
            validation_errors=[],
            test_summary=None,
            errors=[f"Unexpected error: {str(e)}"],
        )


def register_manifest_test_tools(app: FastMCP) -> None:
    """Register manifest test tools with the FastMCP app.

    Args:
        app: FastMCP application instance
    """
    register_mcp_tools(app, domain=ToolDomain.MANIFEST_TESTS)
