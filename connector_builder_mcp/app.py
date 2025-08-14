"""Production-ready ASGI application for FastMCP Cloud deployment.

This module provides a production-optimized ASGI application instance for deploying
the connector-builder-mcp server to FastMCP Cloud and other HTTP-based hosting platforms.
"""

import logging
import os
import sys
from typing import Any

from fastmcp import FastMCP
from fastmcp.server.auth import BearerTokenAuth
from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse

from connector_builder_mcp._connector_builder import register_connector_builder_tools
from connector_builder_mcp._util import initialize_logging


def create_app() -> FastMCP:
    """Create and configure the FastMCP application for production deployment.
    
    Returns:
        FastMCP: Configured FastMCP application instance
    """
    # Initialize logging for production
    initialize_logging()
    logger = logging.getLogger(__name__)
    
    # Configure authentication if token is provided
    auth_token = os.environ.get("MCP_AUTH_TOKEN")
    auth = None
    if auth_token:
        auth = BearerTokenAuth(token=auth_token)
        logger.info("Authentication enabled with bearer token")
    else:
        logger.warning("No MCP_AUTH_TOKEN provided - server will run without authentication")
    
    # Create FastMCP application with optional authentication
    mcp = FastMCP("connector-builder-mcp", auth=auth)
    
    # Register all connector builder tools
    register_connector_builder_tools(mcp)
    
    # Add health check endpoint
    @mcp.custom_route("/health", methods=["GET"])
    async def health_check(request: Request) -> JSONResponse:
        """Health check endpoint for monitoring and load balancers."""
        return JSONResponse({
            "status": "healthy",
            "service": "connector-builder-mcp",
            "version": "1.0.0",
            "transport": "http"
        })
    
    # Add readiness check endpoint
    @mcp.custom_route("/ready", methods=["GET"])
    async def readiness_check(request: Request) -> PlainTextResponse:
        """Readiness check endpoint for container orchestration."""
        return PlainTextResponse("OK")
    
    # Add info endpoint for debugging
    @mcp.custom_route("/info", methods=["GET"])
    async def info_endpoint(request: Request) -> JSONResponse:
        """Information endpoint for debugging and monitoring."""
        return JSONResponse({
            "service": "connector-builder-mcp",
            "description": "MCP server for Airbyte connector building operations",
            "mcp_endpoint": "/mcp",
            "health_endpoint": "/health",
            "ready_endpoint": "/ready",
            "authentication": "enabled" if auth else "disabled",
            "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        })
    
    logger.info("FastMCP application configured for production deployment")
    return mcp


# Create the ASGI application instance
app = create_app()

# Export the ASGI application for deployment
asgi_app = app.http_app()


def main() -> None:
    """Main entry point for running the server directly (development/testing).
    
    For production deployment, use the 'asgi_app' instance with an ASGI server
    like Uvicorn or Gunicorn.
    """
    # Get configuration from environment variables
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", 8000))
    
    print(f"Starting connector-builder-mcp server on {host}:{port}", file=sys.stderr)
    print("For production deployment, use: uvicorn connector_builder_mcp.app:asgi_app", file=sys.stderr)
    
    try:
        # Run the server with HTTP transport
        app.run(transport="http", host=host, port=port)
    except KeyboardInterrupt:
        print("Server interrupted by user.", file=sys.stderr)
    except Exception as ex:
        print(f"Error running server: {ex}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
