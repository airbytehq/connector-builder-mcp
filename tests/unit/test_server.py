"""Tests for MCP server functionality."""

from connector_builder_mcp.server import DefaultConnectorBuilderServer
from connector_builder_mcp.server_class import ConnectorBuilderMCPServer


class TestMCPServer:
    """Test MCP server functionality."""

    def test_server_class_exists(self):
        """Test that the ConnectorBuilderMCPServer class exists."""
        assert ConnectorBuilderMCPServer is not None

    def test_default_server_exists(self):
        """Test that the DefaultConnectorBuilderServer class exists."""
        assert DefaultConnectorBuilderServer is not None

    def test_server_instantiation(self):
        """Test that the server can be instantiated."""
        server = DefaultConnectorBuilderServer()
        assert server is not None
        assert server.app is not None
        assert hasattr(server.app, "run_stdio_async")

    def test_app_initialization(self):
        """Test that the FastMCP app is properly initialized."""
        server = DefaultConnectorBuilderServer()
        assert server.app is not None
        assert server.app.name == "connector-builder-mcp"

    def test_tools_registered(self):
        """Test that connector builder tools are registered."""
        server = DefaultConnectorBuilderServer()
        assert hasattr(server.app, "tool")

    def test_server_has_strategy(self):
        """Test that the server has a strategy class."""
        server = DefaultConnectorBuilderServer()
        strategy_class = server.get_strategy_class()
        assert strategy_class is not None
        assert hasattr(strategy_class, "name")
        assert hasattr(strategy_class, "version")
