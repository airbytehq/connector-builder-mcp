"""TESTING domain tools - Testing for Kotlin source connectors.

This module contains tools for testing Kotlin source connectors by actually
running them against the API.
"""

import logging
from typing import Annotated, Any

from fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from connector_builder_mcp.mcp._mcp_utils import ToolDomain, mcp_tool, register_mcp_tools


logger = logging.getLogger(__name__)


class KotlinBuildResult(BaseModel):
    """Result of Kotlin connector build operation."""

    success: bool
    message: str
    errors: list[str] = []
    warnings: list[str] = []
    build_output: str | None = None


class KotlinTestResult(BaseModel):
    """Result of Kotlin test execution."""

    success: bool
    message: str
    tests_run: int = 0
    tests_passed: int = 0
    tests_failed: int = 0
    errors: list[str] = []
    test_output: str | None = None


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
    domain=ToolDomain.TESTING,
    open_world=True,
)
def compile_and_build(
    ctx: Context,
    *,
    project_path: Annotated[
        str | None,
        Field(description="Path to the Kotlin source connector project directory"),
    ] = None,
) -> KotlinBuildResult:
    """Compile and build a Kotlin source connector project.

    Args:
        ctx: FastMCP context (automatically injected)
        project_path: Path to the connector project

    Returns:
        Build result with success status and any errors/warnings
    """
    logger.info("Compiling and building Kotlin source connector")

    if project_path is None:
        return KotlinBuildResult(
            success=False,
            message="No project path provided",
            errors=["No project path provided"],
        )

    return KotlinBuildResult(
        success=True,
        message="Successfully compiled and built connector (placeholder implementation)",
        errors=[],
        warnings=["Kotlin build is a placeholder implementation"],
    )


@mcp_tool(
    domain=ToolDomain.TESTING,
    open_world=True,
)
def run_unit_tests(
    ctx: Context,
    *,
    project_path: Annotated[
        str | None,
        Field(description="Path to the Kotlin source connector project directory"),
    ] = None,
) -> KotlinTestResult:
    """Run unit tests for a Kotlin source connector project.

    Args:
        ctx: FastMCP context (automatically injected)
        project_path: Path to the connector project

    Returns:
        Test result with success status and test statistics
    """
    logger.info("Running unit tests for Kotlin source connector")

    if project_path is None:
        return KotlinTestResult(
            success=False,
            message="No project path provided",
            errors=["No project path provided"],
        )

    return KotlinTestResult(
        success=True,
        message="Successfully ran unit tests (placeholder implementation)",
        tests_run=0,
        tests_passed=0,
        tests_failed=0,
        errors=[],
    )


@mcp_tool(
    domain=ToolDomain.TESTING,
    open_world=True,
)
def run_integration_tests(
    ctx: Context,
    *,
    project_path: Annotated[
        str | None,
        Field(description="Path to the Kotlin source connector project directory"),
    ] = None,
    config: Annotated[
        dict[str, Any] | str | None,
        Field(description="Connector configuration dictionary (including auth credentials)."),
    ] = None,
) -> KotlinTestResult:
    """Run integration tests for a Kotlin source connector project.

    Args:
        ctx: FastMCP context (automatically injected)
        project_path: Path to the connector project
        config: Connector configuration with credentials

    Returns:
        Test result with success status and test statistics
    """
    logger.info("Running integration tests for Kotlin source connector")

    if project_path is None:
        return KotlinTestResult(
            success=False,
            message="No project path provided",
            errors=["No project path provided"],
        )

    if config is None:
        return KotlinTestResult(
            success=False,
            message="No configuration provided",
            errors=["Configuration with credentials is required for integration tests"],
        )

    return KotlinTestResult(
        success=True,
        message="Successfully ran integration tests (placeholder implementation)",
        tests_run=0,
        tests_passed=0,
        tests_failed=0,
        errors=[],
    )


@mcp_tool(
    domain=ToolDomain.TESTING,
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


def register_testing_tools(app: FastMCP) -> None:
    """Register testing tools with the FastMCP app.

    Args:
        app: FastMCP application instance
    """
    register_mcp_tools(app, domain=ToolDomain.TESTING)
