"""MANIFEST_CHECKS domain tools - Validation for Kotlin destination connectors.

This module contains tools for validating Kotlin destination connector code and
configuration without actually running the connector.
"""

import logging
from typing import Annotated

from fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from connector_builder_mcp.mcp._mcp_utils import ToolDomain, mcp_tool, register_mcp_tools


logger = logging.getLogger(__name__)


class KotlinDestinationValidationResult(BaseModel):
    """Result of Kotlin destination connector validation."""

    is_valid: bool
    errors: list[str] = []
    warnings: list[str] = []
    streams_found: list[str] = []


@mcp_tool(
    ToolDomain.MANIFEST_CHECKS,
    read_only=True,
    idempotent=True,
    open_world=False,
)
def validate_kotlin_destination_connector(
    ctx: Context,
    *,
    project_path: Annotated[
        str | None,
        Field(description="Path to the Kotlin destination connector project directory"),
    ] = None,
) -> KotlinDestinationValidationResult:
    """Validate a Kotlin destination connector project structure and code.

    Args:
        ctx: FastMCP context (automatically injected)
        project_path: Path to the connector project

    Returns:
        Validation result with success status and any errors/warnings
    """
    logger.info("Validating Kotlin destination connector")

    if project_path is None:
        return KotlinDestinationValidationResult(
            is_valid=False,
            errors=["No project path provided"],
            warnings=[],
        )

    errors = []
    warnings = []
    streams_found = []

    warnings.append("Kotlin destination validation is a placeholder implementation")

    is_valid = len(errors) == 0

    return KotlinDestinationValidationResult(
        is_valid=is_valid,
        errors=errors,
        warnings=warnings,
        streams_found=streams_found,
    )


def register_manifest_check_tools(app: FastMCP) -> None:
    """Register manifest check tools with the FastMCP app.

    Args:
        app: FastMCP application instance
    """
    register_mcp_tools(app, domain=ToolDomain.MANIFEST_CHECKS)
