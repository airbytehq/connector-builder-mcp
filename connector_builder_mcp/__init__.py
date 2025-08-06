"""Builder MCP - Model Context Protocol server for Airbyte connector building.

This package provides MCP tools for autonomous AI ownership of connector building processes,
including manifest validation, stream testing, and configuration management.

The focus is on end-to-end AI ownership rather than AI assist, enabling AI agents to
fully control the connector development workflow including testing and PR creation.
"""

from connector_builder_mcp import server


__all__ = ["server"]
__version__ = "0.1.0"
