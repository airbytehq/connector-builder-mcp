"""Builder MCP server implementation.

This module provides the main MCP server for Airbyte connector building operations,
following the PyAirbyte MCP pattern with FastMCP integration.
"""

import asyncio
import sys

from fastmcp import FastMCP

from connector_builder_mcp._util import initialize_logging
from connector_builder_mcp.connector_builder import register_connector_builder_tools
from connector_builder_mcp.encryption import (
    destroy_session_keypair,
    get_public_key_resource,
    initialize_session_keypair,
    is_encryption_enabled,
)


initialize_logging()

app: FastMCP = FastMCP("connector-builder-mcp")
register_connector_builder_tools(app)

# Initialize session keypair if encryption is enabled
initialize_session_keypair()

# Register public key resource if encryption is enabled
if is_encryption_enabled():

    @app.resource("mcp+session://encryption/pubkey")
    def get_session_public_key() -> str:
        """Get the session public key for client-side encryption."""
        return get_public_key_resource()


def main() -> None:
    """Main entry point for the Builder MCP server."""
    print("Starting Builder MCP server.", file=sys.stderr)
    try:
        asyncio.run(app.run_stdio_async())
    except KeyboardInterrupt:
        print("Builder MCP server interrupted by user.", file=sys.stderr)
    except Exception as ex:
        print(f"Error running Builder MCP server: {ex}", file=sys.stderr)
        sys.exit(1)
    finally:
        # Clean up session keypair on shutdown
        destroy_session_keypair()

    print("Builder MCP server stopped.", file=sys.stderr)
    sys.exit(0)


if __name__ == "__main__":
    main()
