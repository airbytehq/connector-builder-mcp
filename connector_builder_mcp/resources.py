# Copyright (c) 2025 Airbyte, Inc., all rights reserved.
"""MCP resources for the Connector Builder MCP server.

This module provides read-only resources that can be accessed by MCP clients.
"""

import importlib.metadata as md
import subprocess
from functools import lru_cache

from fastmcp import FastMCP


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
        "version": version,
        "git_sha": git_sha,
        "fastmcp_version": fastmcp_version,
    }


def register_resources(app: FastMCP) -> None:
    """Register connector builder resources with the FastMCP app.

    Args:
        app: FastMCP application instance
    """

    @app.resource(
        "connector-builder-mcp://version",
        description="Version information for the Connector Builder MCP server",
        mime_type="application/json",
    )
    def version_resource() -> dict[str, str | None]:
        """Resource that returns version information for the MCP server.

        Returns:
            Dictionary with version information
        """
        return _get_version_info()
