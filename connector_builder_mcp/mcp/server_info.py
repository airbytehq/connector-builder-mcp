# Copyright (c) 2025 Airbyte, Inc., all rights reserved.
"""MCP resources for the Connector Builder MCP server.

This module provides read-only resources that can be accessed by MCP clients.
"""

import importlib.metadata as md
import subprocess
from functools import lru_cache

from fastmcp import FastMCP

from connector_builder_mcp.constants import MCP_SERVER_NAME
from connector_builder_mcp.mcp._mcp_utils import ToolDomain, mcp_resource, register_mcp_resources


@lru_cache(maxsize=1)
def _get_version_info() -> dict[str, str | None]:
    """Get version information for the MCP server.

    Returns:
        Dictionary with version information including package version,
        git SHA, and FastMCP version
    """
    package_name = "airbyte-connector-builder-mcp"

    try:
        version = md.version(package_name)
    except md.PackageNotFoundError:
        version = "0.0.0+dev"

    try:
        fastmcp_version = md.version("fastmcp")
    except md.PackageNotFoundError:
        fastmcp_version = None

    try:
        cdk_version = md.version("airbyte-cdk")
    except md.PackageNotFoundError:
        cdk_version = None

    try:
        git_sha = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        ).stdout.strip()
    except Exception:
        git_sha = None

    return {
        "name": package_name,
        "docs_url": "https://github.com/airbytehq/connector-builder-mcp",
        "release_history_url": "https://github.com/airbytehq/connector-builder-mcp/releases",
        "version": version,
        "git_sha": git_sha,
        "fastmcp_version": fastmcp_version,
        "cdk_version": cdk_version,
    }


@mcp_resource(
    uri=f"{MCP_SERVER_NAME}://version",
    description="Version information for the Connector Builder MCP server",
    mime_type="application/json",
    domain=ToolDomain.SERVER_INFO,
)
def mcp_server_info() -> dict[str, str | None]:
    """Resource that returns information for the MCP server.

    This includes package version, release history, help URLs, as well as other information.

    Returns:
        Dictionary with version information
    """
    return _get_version_info()


def register_connector_builder_resources(app: FastMCP) -> None:
    """Register connector builder resources with the FastMCP app.

    Args:
        app: FastMCP application instance
    """
    register_mcp_resources(app, domain=ToolDomain.SERVER_INFO)
