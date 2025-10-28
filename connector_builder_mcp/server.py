"""Builder MCP server implementation.

This module provides the main MCP server for Airbyte connector building operations,
following the PyAirbyte MCP pattern with FastMCP integration.
"""

import asyncio
import sys

from fastmcp import FastMCP

from connector_builder_mcp import prompts as _prompts  # noqa: F401
from connector_builder_mcp import resources as _resources  # noqa: F401
from connector_builder_mcp._util import initialize_logging
from connector_builder_mcp.connector_builder import register_connector_builder_tools
from connector_builder_mcp.mcp_capabilities import (
    register_deferred_prompts,
    register_deferred_resources,
)


initialize_logging()

app: FastMCP = FastMCP("connector-builder-mcp")
register_connector_builder_tools(app)
register_deferred_prompts(app)
register_deferred_resources(app)


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
