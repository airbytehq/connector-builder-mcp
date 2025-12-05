"""Connector Builder MCP Server class for clean subclassing and configuration.

This module provides a base server class that can be subclassed to create
custom connector builder MCP servers with different strategies and configurations.
"""

import asyncio
import logging
import os
import sys
from typing import TYPE_CHECKING

from fastmcp import FastMCP

from connector_builder_mcp.build_strategies.base.build_strategy import BuildStrategy
from connector_builder_mcp.build_strategies.declarative_yaml_v1.build_strategy import (
    DeclarativeYamlV1Strategy,
)
from connector_builder_mcp.constants import MCP_SERVER_NAME
from connector_builder_mcp.mcp.checklist import register_checklist_tools
from connector_builder_mcp.mcp.manifest_edits import register_manifest_edit_tools
from connector_builder_mcp.mcp.manifest_history import register_manifest_history_tools
from connector_builder_mcp.mcp.secrets_config import register_secrets_tools
from connector_builder_mcp.mcp.server_info import register_server_info_resources


if TYPE_CHECKING:
    pass


logger = logging.getLogger(__name__)


class ConnectorBuilderMCPServer:
    """Base class for connector builder MCP servers.

    Subclass this to create custom connector builder servers with
    different strategies and configurations.

    Example:
        ```python
        class MyCustomServer(ConnectorBuilderMCPServer):
            server_name = "my-connector-builder"
            default_strategy_class = MyCustomStrategy

            def prepare_plugin_globals(self) -> None:
                import my_package.server as srv
                srv.mcp = self.app

            def import_plugin_modules(self) -> list[str]:
                return [
                    "my_package.tools.validation",
                    "my_package.tools.testing",
                ]

        def main():
            MyCustomServer().run_stdio(show_banner=False)
        ```

    Attributes:
        server_name: Name of the MCP server (can be overridden in subclass)
        default_strategy_class: Default build strategy class (can be overridden)
        checklist_path: Path to checklist YAML file (can be overridden)
    """

    server_name: str = MCP_SERVER_NAME
    default_strategy_class: type[BuildStrategy] | None = None
    checklist_path: str | None = None

    def __init__(
        self,
        app: FastMCP | None = None,
        *,
        server_name: str | None = None,
        strategy_class: type[BuildStrategy] | None = None,
        checklist_path: str | None = None,
    ) -> None:
        """Initialize the server.

        Args:
            app: Optional FastMCP instance. If not provided, creates one.
            server_name: Override server name (keyword-only)
            strategy_class: Override strategy class (keyword-only)
            checklist_path: Override checklist path (keyword-only)
        """
        if server_name is not None:
            self.server_name = server_name

        if strategy_class is not None:
            self.default_strategy_class = strategy_class

        if checklist_path is not None:
            self.checklist_path = checklist_path

        self.app = app or FastMCP(self.server_name)

    def configure_environment(self) -> None:
        """Configure environment variables before tool registration.

        Sets environment variables that tools may read during registration.
        Subclasses can override to set additional environment variables.
        """
        if self.checklist_path:
            os.environ["CONNECTOR_BUILDER_MCP_CHECKLIST_PATH"] = str(self.checklist_path)
            logger.info(f"Set CONNECTOR_BUILDER_MCP_CHECKLIST_PATH={self.checklist_path}")

    def register_global_tools(self) -> None:
        """Register global tools (checklist, secrets, etc.).

        These tools are strategy-agnostic and available in all server instances.
        Subclasses can override to customize global tool registration.
        """
        logger.info("Registering global tools")
        register_server_info_resources(self.app)
        register_secrets_tools(self.app)
        register_manifest_history_tools(self.app)
        register_checklist_tools(self.app)
        register_manifest_edit_tools(self.app)

    def get_strategy_class(self) -> type[BuildStrategy] | None:
        """Get the build strategy class.

        Returns the strategy class with precedence:
        1. Instance attribute (set via constructor)
        2. Class attribute (set in subclass)
        3. Default fallback (DeclarativeYamlV1Strategy)

        Subclasses can override to provide custom strategy selection logic.

        Returns:
            Build strategy class or None
        """
        if self.default_strategy_class is not None:
            return self.default_strategy_class
        return DeclarativeYamlV1Strategy

    def register_strategy_tools(self) -> None:
        """Register strategy-specific tools.

        Registers tools from the selected build strategy if available.
        Subclasses typically don't need to override this.
        """
        strategy_class = self.get_strategy_class()
        if strategy_class is None:
            logger.warning("No strategy class configured, skipping strategy tool registration")
            return

        if strategy_class.is_available():
            logger.info(
                f"Registering strategy tools: {strategy_class.name} v{strategy_class.version}"
            )
            strategy_class.register_all_mcp_callables(self.app)
        else:
            logger.warning(
                f"Strategy {strategy_class.name} v{strategy_class.version} is not available, "
                "skipping tool registration"
            )

    def prepare_plugin_globals(self) -> None:
        """Prepare global variables before importing plugin modules.

        This is called before import_plugin_modules() to allow subclasses
        to set up global variables (like a global `mcp` instance) that
        plugin modules may reference during import.

        Subclasses should override this to bind their global mcp instance:

        Example:
            ```python
            def prepare_plugin_globals(self) -> None:
                import my_package.server as srv
                srv.mcp = self.app
            ```
        """
        pass

    def import_plugin_modules(self) -> list[str]:
        """Return list of module paths to import for side-effect registration.

        Subclasses should override this to return module paths that use
        decorators (like @mcp.tool) for tool registration.

        Returns:
            List of module paths (e.g., ["my_package.tools.validation"])
        """
        return []

    def register_plugins(self) -> None:
        """Register plugin tools via side-effect imports.

        This method:
        1. Calls prepare_plugin_globals() to set up global variables
        2. Imports each module from import_plugin_modules()

        Subclasses typically don't need to override this.
        """
        self.prepare_plugin_globals()

        plugin_modules = self.import_plugin_modules()
        if plugin_modules:
            logger.info(f"Importing {len(plugin_modules)} plugin module(s)")
            for module_path in plugin_modules:
                logger.debug(f"Importing plugin module: {module_path}")
                __import__(module_path)

    def register_all(self) -> None:
        """Register all tools, prompts, and resources.

        This orchestrates the full registration sequence:
        1. Configure environment variables
        2. Register global tools
        3. Register strategy-specific tools
        4. Register plugin tools

        Subclasses can override to customize the registration order.
        """
        self.configure_environment()
        self.register_global_tools()
        self.register_strategy_tools()
        self.register_plugins()

    def run_stdio(self, show_banner: bool = False) -> None:
        """Run the MCP server with stdio transport.

        Args:
            show_banner: Whether to show startup banner
        """
        self.register_all()

        print("=" * 60, flush=True, file=sys.stderr)
        print(f"Starting {self.server_name} MCP server", file=sys.stderr)

        strategy_class = self.get_strategy_class()
        if strategy_class:
            print(f"Strategy: {strategy_class.name} v{strategy_class.version}", file=sys.stderr)

        print("=" * 60, flush=True, file=sys.stderr)

        try:
            asyncio.run(self.app.run_stdio_async(show_banner=show_banner))
        except KeyboardInterrupt:
            print(f"\n{self.server_name} MCP server interrupted by user.", file=sys.stderr)
        except Exception as ex:
            print(f"Error running {self.server_name} MCP server: {ex}", file=sys.stderr)
            sys.exit(1)

        print(f"{self.server_name} MCP server stopped.", file=sys.stderr)
        print("=" * 60, flush=True, file=sys.stderr)
        sys.exit(0)
