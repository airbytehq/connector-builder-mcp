"""Constants for the Connector Builder MCP server.

This module contains configuration constants and environment variable names
used throughout the Connector Builder MCP server.
"""

import os
import tempfile
from pathlib import Path


CONNECTOR_BUILDER_MCP_SESSION_MANIFEST_PATH = "CONNECTOR_BUILDER_MCP_SESSION_MANIFEST_PATH"
"""Environment variable name for the session manifest file path (most specific).

If set, this environment variable specifies the exact path to the manifest file.
This is the most specific override and takes precedence over all other path settings.
Must be an absolute path. Only allowed in STDIO mode.

Example: /path/to/my/manifest.yaml
"""

CONNECTOR_BUILDER_MCP_SESSION_DIR = "CONNECTOR_BUILDER_MCP_SESSION_DIR"
"""Environment variable name for the session directory (medium specific).

If set, this environment variable specifies the directory where the manifest file
will be stored as manifest.yaml. Takes precedence over SESSION_ROOT but not
SESSION_MANIFEST_PATH. Must be an absolute path. Only allowed in STDIO mode.

Example: /path/to/my/session
Result: /path/to/my/session/manifest.yaml
"""

CONNECTOR_BUILDER_MCP_SESSION_ROOT = "CONNECTOR_BUILDER_MCP_SESSION_ROOT"
"""Environment variable name for the session root directory (least specific).

If set, this environment variable specifies the root directory under which
session-specific subdirectories will be created based on session ID hash.
Takes precedence over the legacy SESSIONS_DIR but not SESSION_DIR or
SESSION_MANIFEST_PATH. Must be an absolute path. Only allowed in STDIO mode.

Example: /path/to/sessions
Result: /path/to/sessions/{session_id_hash}/manifest.yaml
"""

CONNECTOR_BUILDER_MCP_SESSIONS_DIR = "CONNECTOR_BUILDER_MCP_SESSIONS_DIR"
"""Environment variable name for the session storage directory (legacy, deprecated).

DEPRECATED: Use CONNECTOR_BUILDER_MCP_SESSION_ROOT instead.

If set, this environment variable specifies the directory where session-specific
manifest files will be stored. Treated as an alias for SESSION_ROOT with the
lowest precedence. If not set, defaults to a temporary directory.
"""

CONNECTOR_BUILDER_MCP_REMOTE_MODE = "CONNECTOR_BUILDER_MCP_REMOTE_MODE"
"""Environment variable name for remote mode flag.

If set to "true", "1", or "yes" (case-insensitive), indicates the server is
running in remote mode (e.g., SSE/HTTP transport). When remote mode is active,
path override environment variables are not allowed for security reasons.

Default: false (STDIO mode)
"""

SESSION_BASE_DIR = Path(
    os.environ.get(
        CONNECTOR_BUILDER_MCP_SESSIONS_DIR,
        str(Path(tempfile.gettempdir()) / "connector-builder-mcp-sessions"),
    )
)
"""Base directory for session-specific file storage (legacy default).

DEPRECATED: This constant is computed from the legacy CONNECTOR_BUILDER_MCP_SESSIONS_DIR
environment variable. New code should use the resolve_session_manifest_path() function
which respects the full precedence hierarchy of path overrides.

This directory is used to store session-isolated manifest files and other
session-specific data. Each session gets its own subdirectory based on
a hashed session ID.
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
