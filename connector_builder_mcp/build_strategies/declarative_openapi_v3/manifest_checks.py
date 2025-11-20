"""MANIFEST_CHECKS domain tools - Validation for OpenAPI/Sonar connectors.

This module contains tools for validating OpenAPI specifications and connector
configurations without actually running the connector.
"""

import logging
from typing import Annotated

from fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from connector_builder_mcp.build_strategies.declarative_openapi_v3.openapi_to_manifest import (
    generate_manifest_from_openapi,
)
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

    errors: list[str] = []
    warnings: list[str] = []
    resources_found: list[str] = []

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


class ManifestGenerationResult(BaseModel):
    """Result of manifest generation from OpenAPI spec."""

    success: bool
    manifest_yaml: str | None = None
    warnings: list[str] = []
    errors: list[str] = []


@mcp_tool(
    ToolDomain.MANIFEST_CHECKS,
    read_only=True,
    idempotent=True,
    open_world=False,
)
def generate_manifest_from_openapi_spec(
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
) -> ManifestGenerationResult:
    """Generate an Airbyte declarative manifest from an OpenAPI specification.

    This tool converts an OpenAPI 3.0 specification into an Airbyte declarative
    connector manifest. It supports:
    - API Key, Bearer Token, and Basic authentication
    - GET operations that return lists/arrays
    - Automatic pagination detection (offset/limit, page/page_size, cursor)
    - Record selector inference from response schemas

    Args:
        ctx: FastMCP context (automatically injected)
        spec_content: The OpenAPI specification to convert
        source_name: Name for the generated source connector

    Returns:
        Generation result with manifest YAML and any warnings/errors
    """
    logger.info(f"Generating manifest from OpenAPI spec for source: {source_name}")

    try:
        manifest_yaml, warnings = generate_manifest_from_openapi(
            spec_content=spec_content,
            source_name=source_name,
        )

        return ManifestGenerationResult(
            success=True,
            manifest_yaml=manifest_yaml,
            warnings=warnings,
            errors=[],
        )

    except ValueError as e:
        logger.error(f"Failed to generate manifest: {e}")
        return ManifestGenerationResult(
            success=False,
            manifest_yaml=None,
            warnings=[],
            errors=[str(e)],
        )
    except Exception as e:
        logger.exception("Unexpected error generating manifest")
        return ManifestGenerationResult(
            success=False,
            manifest_yaml=None,
            warnings=[],
            errors=[f"Unexpected error: {str(e)}"],
        )


def register_manifest_check_tools(app: FastMCP) -> None:
    """Register manifest check tools with the FastMCP app.

    Args:
        app: FastMCP application instance
    """
    register_mcp_tools(app, domain=ToolDomain.MANIFEST_CHECKS)
