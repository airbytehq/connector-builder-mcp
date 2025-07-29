"""Connector builder MCP tools.

This module provides MCP tools for connector building operations, including
manifest validation, stream testing, and configuration management.
"""

import logging
from typing import Annotated, Any, Literal

from airbyte_cdk.connector_builder.connector_builder_handler import (
    TestLimits,
    create_source,
    get_limits,
    read_stream,
    resolve_manifest,
)
from airbyte_cdk.models import ConfiguredAirbyteCatalog
from fastmcp import FastMCP
from pydantic import BaseModel, Field

from builder_mcp._util import validate_manifest_structure

logger = logging.getLogger(__name__)


class ManifestValidationResult(BaseModel):
    """Result of manifest validation operation."""

    is_valid: bool
    errors: list[str] = []
    warnings: list[str] = []
    resolved_manifest: dict[str, Any] | None = None


class StreamTestResult(BaseModel):
    """Result of stream testing operation."""

    success: bool
    message: str
    records_read: int = 0
    errors: list[str] = []


def validate_manifest(
    manifest: Annotated[
        dict[str, Any],
        Field(description="The connector manifest to validate"),
    ],
    config: Annotated[
        dict[str, Any] | None,
        Field(description="Optional connector configuration for validation"),
    ] = None,
) -> ManifestValidationResult:
    """Validate a connector manifest structure and configuration.

    Args:
        manifest: The connector manifest dictionary to validate
        config: Optional configuration to use for validation

    Returns:
        Validation result with success status and any errors/warnings
    """
    logger.info("Validating connector manifest")

    errors = []
    warnings = []
    resolved_manifest = None

    try:
        if not validate_manifest_structure(manifest):
            errors.append("Manifest missing required fields: version, type, check, streams")
            return ManifestValidationResult(is_valid=False, errors=errors, warnings=warnings)

        if config is None:
            config = {}

        config_with_manifest = {**config, "__injected_declarative_manifest": manifest}

        limits = get_limits(config_with_manifest)
        source = create_source(config_with_manifest, limits)

        resolve_result = resolve_manifest(source)
        if resolve_result.type.value == "RECORD":
            resolved_manifest = resolve_result.record.data.get("manifest")
        else:
            errors.append("Failed to resolve manifest")

    except Exception as e:
        logger.error(f"Error validating manifest: {e}")
        errors.append(f"Validation error: {str(e)}")

    is_valid = len(errors) == 0

    return ManifestValidationResult(
        is_valid=is_valid, errors=errors, warnings=warnings, resolved_manifest=resolved_manifest
    )


def test_stream_read(
    manifest: Annotated[
        dict[str, Any],
        Field(description="The connector manifest"),
    ],
    config: Annotated[
        dict[str, Any],
        Field(description="Connector configuration"),
    ],
    stream_name: Annotated[
        str,
        Field(description="Name of the stream to test"),
    ],
    max_records: Annotated[
        int,
        Field(description="Maximum number of records to read", ge=1, le=1000),
    ] = 10,
) -> StreamTestResult:
    """Test reading from a connector stream.

    Args:
        manifest: The connector manifest
        config: Connector configuration
        stream_name: Name of the stream to test
        max_records: Maximum number of records to read

    Returns:
        Test result with success status and details
    """
    logger.info(f"Testing stream read for stream: {stream_name}")

    try:
        config_with_manifest = {
            **config,
            "__injected_declarative_manifest": manifest,
            "__test_read_config": {
                "max_records": max_records,
                "max_pages_per_slice": 1,
                "max_slices": 1,
                "max_streams": 1,
            },
        }

        limits = get_limits(config_with_manifest)
        source = create_source(config_with_manifest, limits)

        catalog = ConfiguredAirbyteCatalog(streams=[])

        result = read_stream(source, config_with_manifest, catalog, [], limits)

        if result.type.value == "RECORD":
            return StreamTestResult(
                success=True,
                message=f"Successfully read from stream {stream_name}",
                records_read=max_records,
            )
        else:
            error_msg = "Failed to read from stream"
            if hasattr(result, "trace") and result.trace:
                error_msg = result.trace.error.message

            return StreamTestResult(success=False, message=error_msg, errors=[error_msg])

    except Exception as e:
        logger.error(f"Error testing stream read: {e}")
        error_msg = f"Stream test error: {str(e)}"
        return StreamTestResult(success=False, message=error_msg, errors=[error_msg])


def get_resolved_manifest(
    manifest: Annotated[
        dict[str, Any],
        Field(description="The connector manifest to resolve"),
    ],
    config: Annotated[
        dict[str, Any] | None,
        Field(description="Optional connector configuration"),
    ] = None,
) -> dict[str, Any] | Literal["Failed to resolve manifest"]:
    """Get the resolved connector manifest.

    Args:
        manifest: The connector manifest to resolve
        config: Optional configuration for resolution

    Returns:
        Resolved manifest or error message
    """
    logger.info("Getting resolved manifest")

    try:
        if config is None:
            config = {}

        config_with_manifest = {**config, "__injected_declarative_manifest": manifest}

        limits = TestLimits(max_records=10, max_pages_per_slice=1, max_slices=1)

        source = create_source(config_with_manifest, limits)
        result = resolve_manifest(source)

        if result.type.value == "RECORD":
            return result.record.data.get("manifest", {})
        else:
            return "Failed to resolve manifest"

    except Exception as e:
        logger.error(f"Error resolving manifest: {e}")
        return f"Resolution error: {str(e)}"


def register_connector_builder_tools(app: FastMCP) -> None:
    """Register connector builder tools with the FastMCP app.

    Args:
        app: FastMCP application instance
    """
    app.tool()(validate_manifest)
    app.tool()(test_stream_read)
    app.tool()(get_resolved_manifest)
