"""Constants for the Connector Builder MCP server.

This module contains configuration constants and environment variable names
used throughout the Connector Builder MCP server.
"""

import os
import tempfile
from pathlib import Path


CONNECTOR_BUILDER_MCP_SESSIONS_DIR = "CONNECTOR_BUILDER_MCP_SESSIONS_DIR"
"""Environment variable name for the session storage directory.

If set, this environment variable specifies the directory where session-specific
manifest files will be stored. If not set, defaults to a temporary directory.
"""

SESSION_BASE_DIR = Path(
    os.environ.get(
        CONNECTOR_BUILDER_MCP_SESSIONS_DIR,
        str(Path(tempfile.gettempdir()) / "connector-builder-mcp-sessions"),
    )
)
"""Base directory for session-specific file storage.

This directory is used to store session-isolated manifest files and other
session-specific data. Each session gets its own subdirectory based on
a hashed session ID.
"""

MCP_SERVER_NAME = os.environ.get("CONNECTOR_BUILDER_MCP_SERVER_NAME", "connector-builder-mcp")
"""MCP server name used for server identification and resource URIs.

This can be overridden via the CONNECTOR_BUILDER_MCP_SERVER_NAME environment
variable to match the name configured in the client's MCP settings file.

Default: "connector-builder-mcp"
"""

REQUIRE_SESSION_MANIFEST_IN_TOOL_CALLS = True
"""Whether to require a session manifest for tool calls.

If True, tool calls do not allow sending custom file paths or custom
manifest strings. When this is True (default), the scaffolded manifest
tool and the set_session_manifest_text tool must be used to set
the session manifest before calling other tools.

For now, this cannot be overridden by env vars. We will consider adding
that ability in the future if there is a strong use case.
"""
