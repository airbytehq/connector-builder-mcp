"""Builder MCP server implementation with multiple build strategies.

This module provides the main MCP server for Airbyte connector building operations,
supporting multiple build strategies for different connector types.

For custom server implementations, use the ConnectorBuilderMCPServer class from
server_class module instead of directly using this module.
"""

import sys

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
from connector_builder_mcp.constants import CONNECTOR_BUILDER_STRATEGY
from connector_builder_mcp.server_class import ConnectorBuilderMCPServer


initialize_logging()


class DefaultConnectorBuilderServer(ConnectorBuilderMCPServer):
    """Default connector builder server with strategy selection from environment.

    This server implementation supports multiple build strategies and selects
    the active strategy based on the CONNECTOR_BUILDER_STRATEGY environment variable.

    If CONNECTOR_BUILDER_STRATEGY is not set, it uses the first strategy marked
    as default, or falls back to DeclarativeYamlV1Strategy.

    Supported strategies:
    - declarative_yaml_v1 (default)
    - declarative_openapi_v3
    - kotlin_source
    - kotlin_destination
    """

    def get_strategy_class(self):
        """Select strategy based on CONNECTOR_BUILDER_STRATEGY environment variable."""
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

            return selected_strategy

        default_strategies = [s for s in all_strategies if s.is_default]
        if default_strategies:
            return default_strategies[0]

        return DeclarativeYamlV1Strategy


def main() -> None:
    """Main entry point for the Builder MCP server."""
    server = DefaultConnectorBuilderServer()
    server.run_stdio(show_banner=False)


if __name__ == "__main__":
    main()
