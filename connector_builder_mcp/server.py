"""Builder MCP server implementation with multiple build strategies.

This module provides the main MCP server for Airbyte connector building operations,
supporting multiple build strategies for different connector types.
"""

import asyncio
import sys

from fastmcp import FastMCP

from connector_builder_mcp._util import initialize_logging
from connector_builder_mcp.build_strategies.declarative_openapi_v3.build_strategy import (
    DeclarativeOpenApiV3Strategy,
)
from connector_builder_mcp.build_strategies.declarative_yaml_v1.build_strategy import (
    DeclarativeYamlV1Strategy,
)
from connector_builder_mcp.build_strategies.kotlin_destination.build_strategy import (
    KotlinDestinationStrategy,
)
from connector_builder_mcp.build_strategies.kotlin_source.build_strategy import (
    KotlinSourceStrategy,
)
from connector_builder_mcp.constants import CONNECTOR_BUILDER_STRATEGY, MCP_SERVER_NAME
from connector_builder_mcp.mcp.checklist import register_checklist_tools
from connector_builder_mcp.mcp.manifest_edits import register_manifest_edit_tools
from connector_builder_mcp.mcp.manifest_history import register_manifest_history_tools
from connector_builder_mcp.mcp.secrets_config import register_secrets_tools
from connector_builder_mcp.mcp.server_info import register_server_info_resources
from connector_builder_mcp.mcp.smoke_tests import mcp_smoke_tests_prompt  # noqa: F401


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
       - VALIDATION: Validation without running connector
       - TESTING: Testing that runs the connector
       - PROMPTS: Workflow templates

    Args:
        app: FastMCP application instance
    """
    register_server_info_resources(app)
    register_secrets_tools(app)
    register_manifest_history_tools(app)
    register_checklist_tools(app)  # Tools global, YAML files variable
    register_manifest_edit_tools(app)  # Tools global, content variable

    all_strategies = [
        DeclarativeYamlV1Strategy,
        DeclarativeOpenApiV3Strategy,
        KotlinSourceStrategy,
        KotlinDestinationStrategy,
    ]

    # Select active strategy based on environment variable
    if CONNECTOR_BUILDER_STRATEGY:
        selected_strategy = None
        for strategy in all_strategies:
            if strategy.name == CONNECTOR_BUILDER_STRATEGY:
                selected_strategy = strategy
                break

        if selected_strategy is None:
            valid_names = [s.name for s in all_strategies]
            print(
                f"ERROR: Invalid CONNECTOR_BUILDER_STRATEGY='{CONNECTOR_BUILDER_STRATEGY}'. "
                f"Valid values: {', '.join(valid_names)}",
                file=sys.stderr,
            )
            sys.exit(1)

        strategies = [selected_strategy]
        print(
            f"Using strategy from CONNECTOR_BUILDER_STRATEGY: {selected_strategy.name}",
            file=sys.stderr,
        )
    else:
        default_strategies = [s for s in all_strategies if s.is_default]
        if default_strategies:
            strategies = [default_strategies[0]]
            print(f"Using default strategy: {strategies[0].name}", file=sys.stderr)
        else:
            strategies = [DeclarativeYamlV1Strategy]
            print(f"Using fallback strategy: {strategies[0].name}", file=sys.stderr)

    print("Registering build strategies:", file=sys.stderr)
    for strategy in strategies:
        if strategy.is_available():
            print(f"  - {strategy.name} v{strategy.version}", file=sys.stderr)
            strategy.register_all_mcp_callables(app)
        else:
            print(f"  - {strategy.name} v{strategy.version} (unavailable)", file=sys.stderr)


register_server_assets(app)


def main() -> None:
    """Main entry point for the Builder MCP server."""
    print("=" * 60, flush=True, file=sys.stderr)
    print("Starting Builder MCP server with multiple build strategies.", file=sys.stderr)
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
