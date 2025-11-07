"""Builder MCP server implementation.

This module provides the main MCP server for Airbyte connector building operations,
following the PyAirbyte MCP pattern with FastMCP integration.
"""

import asyncio
import sys

from fastmcp import FastMCP

from connector_builder_mcp._util import initialize_logging
from connector_builder_mcp.connector_builder import register_connector_builder_tools
from connector_builder_mcp.prompts import register_prompts
from connector_builder_mcp.resources import register_resources
from connector_builder_mcp.session_manifest import (
    _check_path_overrides_security,
    set_transport_mode,
)


initialize_logging()

set_transport_mode("stdio")

try:
    _check_path_overrides_security()
except RuntimeError as e:
    print(f"FATAL: {e}", file=sys.stderr, flush=True)
    sys.exit(1)

app: FastMCP = FastMCP("connector-builder-mcp")
register_connector_builder_tools(app)
register_prompts(app)
register_resources(app)


def main() -> None:
    """Main entry point for the Builder MCP server."""
    print("=" * 60, flush=True, file=sys.stderr)
    print("Starting Builder MCP server.", file=sys.stderr)
    try:
        asyncio.run(app.run_stdio_async(show_banner=False))
    except KeyboardInterrupt:
        print("Builder MCP server interrupted by user.", file=sys.stderr)
    except Exception as ex:
        print(f"Error running Builder MCP server: {ex}", file=sys.stderr)
        sys.exit(1)

    print("Builder MCP server stopped.", file=sys.stderr)
    print("=" * 60, flush=True, file=sys.stderr)
    sys.exit(0)


if __name__ == "__main__":
    main()
