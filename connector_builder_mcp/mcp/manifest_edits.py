"""MANIFEST_EDITS domain tools - Tools to create, edit, or manage manifests.

This module re-exports manifest editing tools from session_manifest, manifest_history,
manifest_scaffold, and connector_builder modules.
"""

from connector_builder_mcp.connector_builder import get_connector_manifest
from connector_builder_mcp.mcp.manifest_history import (
    diff_session_manifest_versions,
    get_session_manifest_version,
    list_session_manifest_versions,
    restore_session_manifest_version,
)
from connector_builder_mcp.mcp.manifest_scaffold import create_connector_manifest_scaffold
from connector_builder_mcp.mcp.session_manifest import (
    get_session_manifest,
    register_session_manifest_tools,
    set_session_manifest_text,
)


__all__ = [
    "set_session_manifest_text",
    "get_session_manifest",
    "register_session_manifest_tools",
    "list_session_manifest_versions",
    "get_session_manifest_version",
    "diff_session_manifest_versions",
    "restore_session_manifest_version",
    "create_connector_manifest_scaffold",
    "get_connector_manifest",
]
