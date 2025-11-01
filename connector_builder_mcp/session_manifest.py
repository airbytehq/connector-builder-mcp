"""Session-based manifest management for the Connector Builder MCP server.

This module provides session-isolated manifest file storage and management,
allowing multiple concurrent sessions to work with different manifests without conflicts.
"""

import logging
import os
from pathlib import Path
from typing import Annotated, Any

from fastmcp import Context, FastMCP
from pydantic import Field

from connector_builder_mcp.mcp_capabilities import mcp_resource


logger = logging.getLogger(__name__)

DEFAULT_SESSION_ID = "default"

SESSION_BASE_DIR = Path.home() / ".mcp-sessions"


def get_session_id(ctx: Context | None = None) -> str:
    """Get the current session ID from context, environment, or use default.

    Args:
        ctx: Optional FastMCP context (automatically injected in MCP tool calls)

    Returns:
        Session ID string
    """
    if ctx is not None:
        try:
            return ctx.session_id
        except Exception:
            pass
    session_id = os.environ.get("MCP_SESSION_ID", DEFAULT_SESSION_ID)
    logger.debug(f"Using session ID: {session_id}")
    return session_id


def get_session_dir(session_id: str | None = None) -> Path:
    """Get the directory path for a session.

    Args:
        session_id: Optional session ID, defaults to current session

    Returns:
        Path to the session directory
    """
    if session_id is None:
        session_id = get_session_id()

    session_dir = SESSION_BASE_DIR / session_id
    return session_dir


def get_session_manifest_path(session_id: str | None = None) -> Path:
    """Get the path to the session manifest file.

    Args:
        session_id: Optional session ID, defaults to current session

    Returns:
        Path to the manifest.yaml file for the session
    """
    session_dir = get_session_dir(session_id)
    return session_dir / "manifest.yaml"


def session_manifest_exists(session_id: str | None = None) -> bool:
    """Check if a session manifest file exists.

    Args:
        session_id: Optional session ID, defaults to current session

    Returns:
        True if the manifest file exists, False otherwise
    """
    manifest_path = get_session_manifest_path(session_id)
    return manifest_path.exists()


def get_session_manifest_content(session_id: str | None = None) -> str | None:
    """Get the content of the session manifest file.

    Args:
        session_id: Optional session ID, defaults to current session

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
    session_id: str | None = None,
) -> Path:
    """Set the content of the session manifest file.

    Args:
        manifest_yaml: YAML content to write
        session_id: Optional session ID, defaults to current session

    Returns:
        Path to the written manifest file

    Raises:
        Exception: If writing the file fails
    """
    manifest_path = get_session_manifest_path(session_id)

    manifest_path.parent.mkdir(parents=True, exist_ok=True)

    manifest_path.write_text(manifest_yaml, encoding="utf-8")
    logger.info(f"Wrote session manifest to: {manifest_path}")

    return manifest_path


def clear_session_manifest(session_id: str | None = None) -> bool:
    """Clear/delete the session manifest file.

    Args:
        session_id: Optional session ID, defaults to current session

    Returns:
        True if file was deleted, False if it didn't exist
    """
    manifest_path = get_session_manifest_path(session_id)

    if not manifest_path.exists():
        logger.debug(f"Session manifest does not exist, nothing to clear: {manifest_path}")
        return False

    manifest_path.unlink()
    logger.info(f"Cleared session manifest at: {manifest_path}")
    return True


@mcp_resource(
    uri="connector-builder-mcp://session/manifest",
    description="Current session's connector manifest YAML file",
    mime_type="text/yaml",
)
def session_manifest_resource(ctx: Context) -> dict[str, Any]:
    """Resource that exposes the current session's manifest file.

    Args:
        ctx: FastMCP context (automatically injected in MCP resource calls)

    Returns:
        Dictionary with manifest content and metadata
    """
    session_id = get_session_id(ctx)
    manifest_path = get_session_manifest_path(session_id)
    content = get_session_manifest_content(session_id)

    return {
        "session_id": session_id,
        "manifest_path": str(manifest_path.resolve()),
        "exists": content is not None,
        "content": content or "",
    }


def set_session_manifest(
    manifest_yaml: Annotated[
        str,
        Field(description="The connector manifest YAML content to save to the session"),
    ],
    ctx: Context | None = None,
) -> str:
    """Save a connector manifest to the current session.

    This tool stores the manifest YAML in a session-specific file that can be
    referenced by other tools without needing to pass the manifest content repeatedly.

    Args:
        manifest_yaml: The manifest YAML content to save
        ctx: Optional FastMCP context (automatically injected in MCP tool calls)

    Returns:
        Success message with the file path
    """
    logger.info("Setting session manifest")

    session_id = get_session_id(ctx)
    manifest_path = set_session_manifest_content(manifest_yaml, session_id=session_id)

    return f"Successfully saved manifest to session '{session_id}' at: {manifest_path.resolve()}"


def get_session_manifest(ctx: Context | None = None) -> str:
    """Get the connector manifest from the current session.

    Args:
        ctx: Optional FastMCP context (automatically injected in MCP tool calls)

    Returns:
        The manifest YAML content, or an error message if not found
    """
    logger.info("Getting session manifest")

    session_id = get_session_id(ctx)
    content = get_session_manifest_content(session_id)

    if content is None:
        manifest_path = get_session_manifest_path(session_id)
        return f"ERROR: No manifest found for session '{session_id}'. Expected at: {manifest_path.resolve()}"

    return content


def clear_session_manifest_tool(ctx: Context | None = None) -> str:
    """Clear/delete the connector manifest from the current session.

    Args:
        ctx: Optional FastMCP context (automatically injected in MCP tool calls)

    Returns:
        Success message indicating whether the file was deleted
    """
    logger.info("Clearing session manifest")

    session_id = get_session_id(ctx)
    was_deleted = clear_session_manifest(session_id)

    if was_deleted:
        return f"Successfully cleared manifest for session '{session_id}'"
    else:
        return f"No manifest found for session '{session_id}' (nothing to clear)"


def register_session_manifest_tools(app: FastMCP) -> None:
    """Register session manifest tools with the FastMCP app.

    Args:
        app: FastMCP application instance
    """
    app.tool(set_session_manifest)
    app.tool(get_session_manifest)
    app.tool(clear_session_manifest_tool)
