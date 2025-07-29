"""Builder MCP server implementation.

This module provides the main MCP server for Airbyte connector building operations,
following the PyAirbyte MCP pattern with FastMCP integration.
"""

import asyncio
import sys
from typing import NoReturn

from fastmcp import FastMCP

from builder_mcp._connector_builder import register_connector_builder_tools
from builder_mcp._util import initialize_logging

initialize_logging()

app: FastMCP = FastMCP("builder-mcp")
register_connector_builder_tools(app)


def main() -> NoReturn:
    """Main entry point for the Builder MCP server."""
    print("Starting Builder MCP server.", file=sys.stderr)
    try:
        asyncio.run(app.run_stdio_async())
    except KeyboardInterrupt:
        print("Builder MCP server interrupted by user.", file=sys.stderr)
    except Exception as ex:
        print(f"Error running Builder MCP server: {ex}", file=sys.stderr)
        sys.exit(1)

    print("Builder MCP server stopped.", file=sys.stderr)


if __name__ == "__main__":
    main()
