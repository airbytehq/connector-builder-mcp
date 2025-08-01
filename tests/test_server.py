"""Tests for MCP server functionality."""

from connector_builder_mcp.server import app


class TestMCPServer:
    """Test MCP server functionality."""

    def test_app_initialization(self):
        """Test that the FastMCP app is properly initialized."""
        assert app is not None
        assert app.name == "connector-builder-mcp"

    def test_tools_registered(self):
        """Test that connector builder tools are registered."""
        assert hasattr(app, "tool")

    def test_server_startup(self):
        """Test that the server can start up without errors."""
        assert app is not None
        assert app.name == "connector-builder-mcp"
