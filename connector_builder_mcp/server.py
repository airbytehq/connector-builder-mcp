"""Builder MCP server implementation.

This module provides the main MCP server for Airbyte connector building operations,
following the PyAirbyte MCP pattern with FastMCP integration.
"""

import asyncio
import signal
import sys

import anyio
from fastmcp import FastMCP

from connector_builder_mcp._util import initialize_logging
from connector_builder_mcp.connector_builder import register_connector_builder_tools


initialize_logging()

app: FastMCP = FastMCP("connector-builder-mcp")
register_connector_builder_tools(app)


def main() -> None:
    """Main entry point for the Builder MCP server."""
    print("Starting Builder MCP server.", file=sys.stderr)
    
    async def run_server():
        """Run the server with proper signal handling."""
        shutdown_event = asyncio.Event()
        
        def signal_handler():
            print("Builder MCP server interrupted by user.", file=sys.stderr)
            shutdown_event.set()
        
        if sys.platform != "win32":
            loop = asyncio.get_running_loop()
            for sig in (signal.SIGTERM, signal.SIGINT):
                loop.add_signal_handler(sig, signal_handler)
        
        try:
            async with anyio.create_task_group() as tg:
                tg.start_soon(app.run_stdio_async)
                await shutdown_event.wait()
                tg.cancel_scope.cancel()
        except anyio.get_cancelled_exc_class():
            pass
        except Exception as ex:
            print(f"Error running Builder MCP server: {ex}", file=sys.stderr)
            sys.exit(1)
    
    try:
        asyncio.run(run_server())
    except KeyboardInterrupt:
        print("Builder MCP server interrupted by user.", file=sys.stderr)
    
    print("Builder MCP server stopped.", file=sys.stderr)
    sys.exit(0)


if __name__ == "__main__":
    main()
