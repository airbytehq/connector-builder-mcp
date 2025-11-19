"""MANIFEST_CHECKS domain tools - Validation for OpenAPI/Sonar connectors.

This module contains tools for validating OpenAPI specifications and connector
configurations without actually running the connector.
"""

import logging
from typing import Annotated

from fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from connector_builder_mcp.mcp._mcp_utils import ToolDomain, mcp_tool, register_mcp_tools


logger = logging.getLogger(__name__)


class OpenApiValidationResult(BaseModel):
    """Result of OpenAPI specification validation."""

    is_valid: bool
    errors: list[str] = []
    warnings: list[str] = []
    resources_found: list[str] = []


@mcp_tool(
    ToolDomain.MANIFEST_CHECKS,
    read_only=True,
    idempotent=True,
    open_world=False,
)
def validate_openapi_spec(
    ctx: Context,
    *,
    spec_content: Annotated[
        str | None,
        Field(
            description="The OpenAPI specification content (YAML or JSON). "
            "Can be raw content or path to spec file."
        ),
    ] = None,
) -> OpenApiValidationResult:
    """Validate an OpenAPI specification for connector building.

    Args:
        ctx: FastMCP context (automatically injected)
        spec_content: The OpenAPI specification to validate

    Returns:
        Validation result with success status and any errors/warnings
    """
    logger.info("Validating OpenAPI specification")

    if spec_content is None:
        return OpenApiValidationResult(
            is_valid=False,
            errors=["No OpenAPI specification provided"],
            warnings=[],
        )

    errors = []
    warnings = []
    resources_found = []

    if len(spec_content) < 10:
        errors.append("OpenAPI specification appears to be empty or too short")

    if "openapi" not in spec_content.lower():
        errors.append("Missing 'openapi' version field")

    if "paths" not in spec_content.lower():
        warnings.append("No 'paths' section found in specification")

    if "x-airbyte" not in spec_content:
        warnings.append(
            "No x-airbyte-* extensions found. You may need to add these to define resources."
        )

    is_valid = len(errors) == 0

    return OpenApiValidationResult(
        is_valid=is_valid,
        errors=errors,
        warnings=warnings,
        resources_found=resources_found,
    )


def register_manifest_check_tools(app: FastMCP) -> None:
    """Register manifest check tools with the FastMCP app.

    Args:
        app: FastMCP application instance
    """
    register_mcp_tools(app, domain=ToolDomain.MANIFEST_CHECKS)
