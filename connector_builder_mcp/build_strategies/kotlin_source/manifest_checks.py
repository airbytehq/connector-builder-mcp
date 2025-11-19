"""MANIFEST_CHECKS domain tools - Validation for Kotlin source connectors.

This module contains tools for validating Kotlin source connector code and
configuration without actually running the connector.
"""

import logging
from typing import Annotated

from fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from connector_builder_mcp.mcp._mcp_utils import ToolDomain, mcp_tool, register_mcp_tools


logger = logging.getLogger(__name__)


class KotlinSourceValidationResult(BaseModel):
    """Result of Kotlin source connector validation."""

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
def validate_kotlin_source_connector(
    ctx: Context,
    *,
    project_path: Annotated[
        str | None,
        Field(description="Path to the Kotlin source connector project directory"),
    ] = None,
) -> KotlinSourceValidationResult:
    """Validate a Kotlin source connector project structure and code.

    Args:
        ctx: FastMCP context (automatically injected)
        project_path: Path to the connector project

    Returns:
        Validation result with success status and any errors/warnings
    """
    logger.info("Validating Kotlin source connector")

    if project_path is None:
        return KotlinSourceValidationResult(
            is_valid=False,
            errors=["No project path provided"],
            warnings=[],
        )

    errors: list[str] = []
    warnings: list[str] = []
    streams_found: list[str] = []

    warnings.append("Kotlin source validation is a placeholder implementation")

    is_valid = len(errors) == 0

    return KotlinSourceValidationResult(
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
