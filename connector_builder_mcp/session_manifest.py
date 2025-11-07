"""Session-based manifest management for the Connector Builder MCP server.

This module provides session-isolated manifest file storage and management,
allowing multiple concurrent sessions to work with different manifests without conflicts.
"""

import hashlib
import logging
import os
import tempfile
from functools import lru_cache
from pathlib import Path
from typing import Annotated

from fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from connector_builder_mcp.mcp_capabilities import mcp_resource, mcp_tool, register_deferred_tools


logger = logging.getLogger(__name__)

SESSION_BASE_DIR = Path(
    os.environ.get(
        "CONNECTOR_BUILDER_MCP_SESSIONS_DIR",
        str(Path(tempfile.gettempdir()) / "connector-builder-mcp-sessions"),
    )
)


class SessionManifestResource(BaseModel):
    """Response model for the session manifest resource."""

    session_id: str
    manifest_path: str
    exists: bool
    content: str


def _sanitize_session_id(session_id: str) -> str:
    """Sanitize session ID to ensure it's filesystem-safe.

    Args:
        session_id: Raw session ID

    Returns:
        Filesystem-safe session ID (hashed)
    """
    return hashlib.sha256(session_id.encode()).hexdigest()


@lru_cache(maxsize=256)
def get_session_dir(session_id: str) -> Path:
    """Get the directory path for a session, ensuring it exists.

    This function is LRU cached to avoid repeated filesystem operations.
    The directory is created if it doesn't exist.

    Args:
        session_id: Session ID

    Returns:
        Path to the session directory (guaranteed to exist)
    """
    sanitized_id = _sanitize_session_id(session_id)
    session_dir = SESSION_BASE_DIR / sanitized_id
    session_dir.mkdir(parents=True, exist_ok=True)
    return session_dir


def get_session_manifest_path(session_id: str) -> Path:
    """Get the path to the session manifest file.

    Args:
        session_id: Session ID

    Returns:
        Path to the manifest.yaml file for the session
    """
    session_dir = get_session_dir(session_id)
    return session_dir / "manifest.yaml"


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
) -> Path:
    """Set the content of the session manifest file.

    Args:
        manifest_yaml: YAML content to write
        session_id: Session ID

    Returns:
        Path to the written manifest file

    Raises:
        Exception: If writing the file fails
    """
    manifest_path = get_session_manifest_path(session_id)

    manifest_path.write_text(manifest_yaml, encoding="utf-8")
    logger.info(f"Wrote session manifest to: {manifest_path}")

    return manifest_path


@mcp_resource(
    uri="connector-builder-mcp://session/manifest",
    description="Current session's connector manifest and metadata",
    mime_type="application/json",
)
def session_manifest_resource(ctx: Context) -> SessionManifestResource:
    """Resource that exposes the current session's manifest file.

    Args:
        ctx: FastMCP context (automatically injected in MCP resource calls)

    Returns:
        SessionManifestResource with manifest content and metadata
    """
    session_id = ctx.session_id
    manifest_path = get_session_manifest_path(session_id)
    content = get_session_manifest_content(session_id)

    return SessionManifestResource(
        session_id=session_id,
        manifest_path=str(manifest_path.resolve()),
        exists=content is not None,
        content=content or "",
    )


@mcp_tool()
def set_session_manifest(
    manifest_yaml: Annotated[
        str,
        Field(description="The connector manifest YAML content to save to the session"),
    ],
    ctx: Context,
) -> str:
    """Save a connector manifest to the current session.

    This tool stores the manifest YAML in a session-specific file that can be
    referenced by other tools without needing to pass the manifest content repeatedly.

    Args:
        manifest_yaml: The manifest YAML content to save
        ctx: FastMCP context (automatically injected in MCP tool calls)

    Returns:
        Success message with the file path
    """
    logger.info("Setting session manifest")

    session_id = ctx.session_id
    manifest_path = set_session_manifest_content(manifest_yaml, session_id=session_id)

    return f"Successfully saved manifest to session '{session_id}' at: {manifest_path.resolve()}"


@mcp_tool()
def get_session_manifest(ctx: Context) -> str:
    """Get the connector manifest from the current session.

    Args:
        ctx: FastMCP context (automatically injected in MCP tool calls)

    Returns:
        The manifest YAML content, or an error message if not found
    """
    logger.info("Getting session manifest")

    session_id = ctx.session_id
    content = get_session_manifest_content(session_id)

    if content is None:
        manifest_path = get_session_manifest_path(session_id)
        return f"ERROR: No manifest found for session '{session_id}'. Expected at: {manifest_path.resolve()}"

    return content


def register_session_manifest_tools(app: FastMCP) -> None:
    """Register session manifest tools with the FastMCP app.

    Args:
        app: FastMCP application instance
    """
    register_deferred_tools(app)
