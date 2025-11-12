"""Builder MCP server implementation (declarative YAML strategy).

This module provides the main MCP server for Airbyte connector building operations,
using the declarative YAML v1 build strategy.
"""

import asyncio
import sys

from fastmcp import FastMCP

from connector_builder_mcp._util import initialize_logging
from connector_builder_mcp.build_strategies.declarative_yaml_v1.build_strategy import (
    DeclarativeYamlV1Strategy,
)
from connector_builder_mcp.constants import MCP_SERVER_NAME
from connector_builder_mcp.mcp.checklist import register_checklist_tools
from connector_builder_mcp.mcp.manifest_edits import register_manifest_edit_tools
from connector_builder_mcp.mcp.manifest_history import register_manifest_history_tools
from connector_builder_mcp.mcp.secrets_config import register_secrets_tools
from connector_builder_mcp.mcp.server_info import register_server_info_resources


initialize_logging()

app: FastMCP = FastMCP(MCP_SERVER_NAME)


def register_server_assets(app: FastMCP) -> None:
    """Register all server assets (tools, prompts, resources) with the FastMCP app.

    This function registers assets in two categories:

    1. Global domains (same for all strategies):
       - SERVER_INFO: Server version and information resources
       - SECRETS_CONFIG: Manage secrets and configuration
       - MANIFEST_HISTORY: View or manage manifest revision history
       - CHECKLIST: Task tracking (tools global, YAML files variable)
       - MANIFEST_EDITS: Manifest operations (tools global, content variable)

    2. Variable domains (strategy-specific):
       - GUIDANCE: Documentation and examples
       - MANIFEST_CHECKS: Validation without running connector
       - MANIFEST_TESTS: Testing that runs the connector
       - PROMPTS: Workflow templates

    Args:
        app: FastMCP application instance
    """
    register_server_info_resources(app)
    register_secrets_tools(app)
    register_manifest_history_tools(app)
    register_checklist_tools(app)  # Tools global, YAML files variable
    register_manifest_edit_tools(app)  # Tools global, content variable

    strategy = DeclarativeYamlV1Strategy
    print(f"Using build strategy: {strategy.name} v{strategy.version}", file=sys.stderr)
    strategy.register_all_mcp_callables(app)


register_server_assets(app)


def main() -> None:
    """Main entry point for the Builder MCP server."""
    print("=" * 60, flush=True, file=sys.stderr)
    print("Starting Builder MCP server (declarative YAML v1).", file=sys.stderr)
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
