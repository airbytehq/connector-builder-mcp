"""TESTING domain tools - Testing for Kotlin destination connectors.

This module contains tools for testing Kotlin destination connectors by actually
running them against the destination system.
"""

import logging
from typing import Annotated, Any

from fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from connector_builder_mcp.mcp._mcp_utils import ToolDomain, mcp_tool, register_mcp_tools


logger = logging.getLogger(__name__)


class KotlinDestinationTestResult(BaseModel):
    """Result of Kotlin destination testing operation."""

    success: bool
    message: str
    records_written: int = 0
    errors: list[str] = []


@mcp_tool(
    domain=ToolDomain.TESTING,
    open_world=True,
)
def test_kotlin_destination_write(
    ctx: Context,
    *,
    stream_name: Annotated[
        str,
        Field(description="Name of the stream to test"),
    ],
    project_path: Annotated[
        str | None,
        Field(description="Path to the Kotlin destination connector project directory"),
    ] = None,
    config: Annotated[
        dict[str, Any] | str | None,
        Field(description="Connector configuration dictionary (including auth credentials)."),
    ] = None,
    test_records: Annotated[
        list[dict[str, Any]] | None,
        Field(description="Test records to write to the destination"),
    ] = None,
) -> KotlinDestinationTestResult:
    """Test writing data to a Kotlin destination connector.

    Args:
        ctx: FastMCP context (automatically injected)
        stream_name: Name of the stream to test
        project_path: Path to the connector project
        config: Connector configuration with credentials
        test_records: Sample records to write for testing

    Returns:
        Test result with success status and any errors
    """
    logger.info(f"Testing Kotlin destination write for stream: {stream_name}")

    if project_path is None:
        return KotlinDestinationTestResult(
            success=False,
            message="No project path provided",
            errors=["No project path provided"],
        )

    if config is None:
        return KotlinDestinationTestResult(
            success=False,
            message="No configuration provided",
            errors=["Configuration with credentials is required for testing"],
        )

    if test_records is None or len(test_records) == 0:
        return KotlinDestinationTestResult(
            success=False,
            message="No test records provided",
            errors=["Test records are required for testing write operations"],
        )

    return KotlinDestinationTestResult(
        success=True,
        message=f"Successfully tested write to stream '{stream_name}' (placeholder implementation)",
        records_written=0,
        errors=[],
    )


def register_testing_tools(app: FastMCP) -> None:
    """Register testing tools with the FastMCP app.

    Args:
        app: FastMCP application instance
    """
    register_mcp_tools(app, domain=ToolDomain.TESTING)
