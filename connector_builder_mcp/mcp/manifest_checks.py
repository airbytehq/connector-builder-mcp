"""MANIFEST_CHECKS domain tools - Validation that doesn't run the connector.

This module contains tools for validating manifest structure and syntax
without actually running the connector.
"""

import logging
from typing import Annotated

from fastmcp import Context
from pydantic import Field

from connector_builder_mcp._validation_helpers import validate_manifest_content
from connector_builder_mcp.mcp._mcp_utils import ToolDomain, mcp_tool
from connector_builder_mcp.mcp.manifest_edits import get_session_manifest_content
from connector_builder_mcp.mcp.manifest_history import (
    CheckpointType,
    ValidationCheckpointDetails,
    _checkpoint_manifest_revision,
)
from connector_builder_mcp.mcp.manifest_tests import ManifestValidationResult
from connector_builder_mcp.mcp._mcp_utils import register_mcp_tools


logger = logging.getLogger(__name__)


@mcp_tool(
    ToolDomain.MANIFEST_CHECKS,
    read_only=True,
    idempotent=True,
    open_world=False,
)
def validate_manifest(
    ctx: Context,
    *,
    manifest: Annotated[
        str | None,
        Field(
            description="The connector manifest to validate. "
            "Can be raw a YAML string or path to YAML file. "
            "If not provided, uses the session manifest."
        ),
    ] = None,
) -> ManifestValidationResult:
    """Validate a connector manifest structure and configuration.

    Args:
        ctx: FastMCP context (automatically injected)
        manifest: The connector manifest to validate (optional, uses session manifest if not provided)

    Returns:
        Validation result with success status and any errors/warnings
    """
    logger.info("Validating connector manifest")

    if manifest is None:
        manifest = get_session_manifest_content(ctx.session_id)
        if manifest is None:
            return ManifestValidationResult(
                is_valid=False,
                errors=[
                    "No manifest provided and no session manifest found. "
                    "Either provide a manifest or use set_session_manifest_text() to save one."
                ],
                warnings=[],
            )
        logger.info("Using session manifest for validation")

    is_valid, errors, warnings, resolved_manifest = validate_manifest_content(manifest)

    checkpoint_type = CheckpointType.VALIDATION_PASS if is_valid else CheckpointType.VALIDATION_FAIL
    checkpoint_details = ValidationCheckpointDetails(
        error_count=len(errors),
        warning_count=len(warnings),
        errors=errors[:5] if errors else [],
    )
    _checkpoint_manifest_revision(
        session_id=ctx.session_id,
        checkpoint_type=checkpoint_type,
        checkpoint_details=checkpoint_details,
    )

    return ManifestValidationResult(
        is_valid=is_valid,
        errors=errors,
        warnings=warnings,
        resolved_manifest=resolved_manifest,
    )


def register_manifest_check_tools(app) -> None:
    """Register manifest check tools with the FastMCP app.

    Args:
        app: FastMCP application instance
    """
    register_mcp_tools(app, domain=ToolDomain.MANIFEST_CHECKS)
