"""Session-based manifest management for the Connector Builder MCP server.

This module provides session-isolated manifest file storage and management,
allowing multiple concurrent sessions to work with different manifests without conflicts.
"""

import logging
from pathlib import Path

from fastmcp import Context, FastMCP
from pydantic import BaseModel

from connector_builder_mcp._paths import get_session_manifest_path
from connector_builder_mcp.constants import MCP_SERVER_NAME
from connector_builder_mcp.manifest_history import save_manifest_revision
from connector_builder_mcp.mcp._tool_utils import ToolDomain, register_tools
from connector_builder_mcp.mcp_capabilities import mcp_resource


logger = logging.getLogger(__name__)


class SetManifestContentsResult(BaseModel):
    """Result of setting session manifest text."""

    message: str
    revision_id: tuple[int, int, str] | None = None  # (ordinal, timestamp_ns, content_hash)
    diff_summary: str | None = None
    validation_warnings: list[str] = []
    error: str | None = None


def get_session_manifest_content(session_id: str) -> str | None:
    """Get the content of the session manifest file.

    Args:
        session_id: Session ID

    Returns:
        Manifest YAML content as string, or None if file doesn't exist
    """
    manifest_path = get_session_manifest_path(session_id)

    if not manifest_path.exists():
        logger.debug(f"Session manifest does not exist at: {manifest_path}")
        return None

    try:
        content = manifest_path.read_text(encoding="utf-8")
        logger.info(f"Read session manifest from: {manifest_path}")
        return content
    except Exception as e:
        logger.error(f"Error reading session manifest from {manifest_path}: {e}")
        return None


def set_session_manifest_content(
    manifest_yaml: str,
    session_id: str,
) -> tuple[Path, tuple[int, int, str]]:
    """Set the content of the session manifest file.

    Returns:
        Tuple of (path to written manifest file, revision ID triple)

    Raises:
        Exception: If writing the file fails
    """
    manifest_path = get_session_manifest_path(session_id)

    manifest_path.write_text(manifest_yaml, encoding="utf-8")
    logger.info(f"Wrote session manifest to: {manifest_path}")

    revision_id = save_manifest_revision(session_id=session_id, content=manifest_yaml)

    return manifest_path, revision_id


@mcp_resource(
    uri=f"{MCP_SERVER_NAME}://session/manifest",
    description="Current session's connector manifest YAML content",
    mime_type="text/yaml",
)
def session_manifest_yaml_contents(ctx: Context) -> str:
    """Resource that exposes the current session's manifest file.

    This resource returns the raw YAML manifest content as a string.
    For metadata like session ID and file path, use the get_session_manifest tool instead.

    Args:
        ctx: FastMCP context (automatically injected in MCP resource calls)

    Returns:
        The manifest YAML content as a string, or empty string if not found
    """
    session_id = ctx.session_id
    content = get_session_manifest_content(session_id)
    return content or ""


def register_session_manifest_tools(app: FastMCP) -> None:
    """Register session manifest tools with the FastMCP app.

    Args:
        app: FastMCP application instance
    """
    register_tools(app, ToolDomain.MANIFEST_EDITS)
