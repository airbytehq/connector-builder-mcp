"""Builder MCP server implementation.

This module provides the main MCP server for Airbyte connector building operations,
following the PyAirbyte MCP pattern with FastMCP integration.
"""

import asyncio
import sys

from fastmcp import FastMCP

from connector_builder_mcp._util import initialize_logging
from connector_builder_mcp.constants import MCP_SERVER_NAME
from connector_builder_mcp.mcp._mcp_utils import ToolDomain
from connector_builder_mcp.mcp.checklist import register_checklist_tools
from connector_builder_mcp.mcp.guidance import register_guidance_tools
from connector_builder_mcp.mcp.manifest_checks import register_manifest_check_tools
from connector_builder_mcp.mcp.manifest_edits import register_manifest_edit_tools
from connector_builder_mcp.mcp.manifest_history import register_manifest_history_tools
from connector_builder_mcp.mcp.manifest_tests import register_manifest_test_tools
from connector_builder_mcp.mcp.prompts import register_mcp_prompts
from connector_builder_mcp.mcp.secrets_config import register_secrets_tools
from connector_builder_mcp.mcp.server_info import register_server_info_resources


initialize_logging()

app: FastMCP = FastMCP(MCP_SERVER_NAME)


def register_server_assets(app: FastMCP) -> None:
    """Register all server assets (tools, prompts, resources) with the FastMCP app.

    This function registers assets from all domains:
    - GUIDANCE: Checklist, docs, schema, find connectors
    - MANIFEST_CHECKS: Validation without running connector
    - MANIFEST_TESTS: Testing that runs the connector
    - MANIFEST_EDITS: Create, edit, manage manifests
    - SECRETS_CONFIG: Manage secrets and configuration
    - SERVER_INFO: Server version and information resources

    Args:
        app: FastMCP application instance
    """
    register_checklist_tools(app)
    register_guidance_tools(app)
    register_manifest_edit_tools(app)
    register_manifest_check_tools(app)
    register_manifest_test_tools(app)
    register_secrets_tools(app)
    register_manifest_history_tools(app)
    register_mcp_prompts(app, domain=ToolDomain.PROMPTS)
    register_server_info_resources(app)


register_server_assets(app)


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
