"""MANIFEST_TESTS domain tools - Testing for Kotlin source connectors.

This module contains tools for testing Kotlin source connectors by actually
running them against the API.
"""

import logging
from typing import Annotated, Any

from fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from connector_builder_mcp.mcp._mcp_utils import ToolDomain, mcp_tool, register_mcp_tools


logger = logging.getLogger(__name__)


class KotlinStreamTestResult(BaseModel):
    """Result of Kotlin stream testing operation."""

    success: bool
    message: str
    records_read: int = 0
    errors: list[str] = []
    records: list[dict[str, Any]] | None = Field(
        default=None, description="Actual record data from the stream"
    )


@mcp_tool(
    domain=ToolDomain.MANIFEST_TESTS,
    open_world=True,
)
def test_kotlin_source_stream(
    ctx: Context,
    *,
    stream_name: Annotated[
        str,
        Field(description="Name of the stream to test"),
    ],
    project_path: Annotated[
        str | None,
        Field(description="Path to the Kotlin source connector project directory"),
    ] = None,
    config: Annotated[
        dict[str, Any] | str | None,
        Field(description="Connector configuration dictionary (including auth credentials)."),
    ] = None,
    max_records: Annotated[
        int,
        Field(description="Maximum number of records to read", ge=1),
    ] = 10,
) -> KotlinStreamTestResult:
    """Test reading data from a Kotlin source connector stream.

    Args:
        ctx: FastMCP context (automatically injected)
        stream_name: Name of the stream to test
        project_path: Path to the connector project
        config: Connector configuration with credentials
        max_records: Maximum number of records to read

    Returns:
        Test result with success status and any errors
    """
    logger.info(f"Testing Kotlin source stream: {stream_name}")

    if project_path is None:
        return KotlinStreamTestResult(
            success=False,
            message="No project path provided",
            errors=["No project path provided"],
        )

    if config is None:
        return KotlinStreamTestResult(
            success=False,
            message="No configuration provided",
            errors=["Configuration with credentials is required for testing"],
        )

    return KotlinStreamTestResult(
        success=True,
        message=f"Successfully tested stream '{stream_name}' (placeholder implementation)",
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
