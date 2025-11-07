"""Session-based manifest management for the Connector Builder MCP server.

This module provides session-isolated manifest file storage and management,
allowing multiple concurrent sessions to work with different manifests without conflicts.
"""

import hashlib
import logging
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from connector_builder_mcp._tool_utils import ToolDomain, mcp_tool, register_tools
from connector_builder_mcp.constants import SESSION_BASE_DIR
from connector_builder_mcp.mcp_capabilities import mcp_resource


logger = logging.getLogger(__name__)


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


def _apply_text_edit(
    existing: str,
    mode: Literal["replace_all", "replace_lines", "insert_lines"],
    manifest_yaml: str,
    insert_at_line_number: int | None,
    replace_lines: tuple[int, int] | None,
) -> str | tuple[str, str]:
    """Apply text edit to existing content based on mode.

    Args:
        existing: Existing manifest content (empty string if no manifest exists)
        mode: Edit mode ('replace_all', 'replace_lines', or 'insert_lines')
        manifest_yaml: Content to insert or use for replacement
        insert_at_line_number: Line number to insert before (1-indexed, for insert_lines mode)
        replace_lines: (start_line, end_line) tuple (1-indexed, inclusive, for replace_lines mode)

    Returns:
        Modified content string, or tuple of ("ERROR: ...", error_message) on validation failure
    """
    valid_modes = ["replace_all", "replace_lines", "insert_lines"]
    if mode not in valid_modes:
        return ("ERROR", f"ERROR: mode must be one of {valid_modes}")

    if mode == "replace_all":
        if insert_at_line_number is not None:
            return ("ERROR", "ERROR: mode='replace_all' cannot be used with insert_at_line_number")
        if replace_lines is not None:
            return ("ERROR", "ERROR: mode='replace_all' cannot be used with replace_lines")
        return manifest_yaml

    lines = existing.splitlines(keepends=True)
    num_lines = len(lines)

    if mode == "replace_lines":
        if replace_lines is None:
            return (
                "ERROR",
                "ERROR: mode='replace_lines' requires replace_lines=(start,end) tuple",
            )
        if insert_at_line_number is not None:
            return (
                "ERROR",
                "ERROR: mode='replace_lines' cannot be used with insert_at_line_number",
            )

        start_line, end_line = replace_lines

        if not (1 <= start_line <= end_line):
            return (
                "ERROR",
                f"ERROR: replace_lines requires 1 <= start_line <= end_line, got start={start_line}, end={end_line}",
            )
        if end_line > num_lines:
            return (
                "ERROR",
                f"ERROR: replace_lines end_line={end_line} exceeds file length ({num_lines} lines)",
            )

        start_idx = start_line - 1
        end_idx = end_line  # end_line is inclusive, so end_idx is exclusive

        replacement_lines = manifest_yaml.splitlines(keepends=True)

        new_lines = lines[:start_idx] + replacement_lines + lines[end_idx:]
        return "".join(new_lines)

    if mode == "insert_lines":
        if insert_at_line_number is None:
            return (
                "ERROR",
                f"ERROR: mode='insert_lines' requires insert_at_line_number (1..{num_lines + 1})",
            )
        if replace_lines is not None:
            return ("ERROR", "ERROR: mode='insert_lines' cannot be used with replace_lines")

        if not (1 <= insert_at_line_number <= num_lines + 1):
            return (
                "ERROR",
                f"ERROR: insert_at_line_number must be in range 1..{num_lines + 1}, got {insert_at_line_number}",
            )

        insert_idx = insert_at_line_number - 1

        insert_lines = manifest_yaml.splitlines(keepends=True)

        new_lines = lines[:insert_idx] + insert_lines + lines[insert_idx:]
        return "".join(new_lines)

    return ("ERROR", f"ERROR: Unexpected mode: {mode}")


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


@mcp_tool(
    ToolDomain.MANIFEST_EDITS,
    read_only=False,
    destructive=False,
    idempotent=False,
    open_world=False,
)
def set_session_manifest_text(
    ctx: Context,
    *,
    mode: Annotated[
        Literal["replace_all", "replace_lines", "insert_lines"],
        Field(
            description="Edit mode: 'replace_all' (overwrite entire file), 'replace_lines' (replace specific line range), or 'insert_lines' (insert before specific line)"
        ),
    ],
    manifest_yaml: Annotated[
        str,
        Field(
            description="The connector manifest YAML content to save, insert, or use for replacement"
        ),
    ],
    insert_at_line_number: Annotated[
        int | None,
        Field(
            description="Line number to insert before (1-indexed, required for insert_lines mode, valid range: 1 to num_lines+1)"
        ),
    ] = None,
    replace_lines: Annotated[
        tuple[int, int] | None,
        Field(
            description="(start_line, end_line) tuple for replacement (1-indexed, inclusive, required for replace_lines mode)"
        ),
    ] = None,
) -> str:
    """Save or edit a connector manifest in the current session.

    This tool supports three modes for updating the session manifest:

    1. **replace_all**: Overwrites the entire manifest file with new content.
       - Use manifest_yaml to provide the full new content
       - To clear the manifest, use mode='replace_all' with manifest_yaml=""
       - Cannot be used with insert_at_line_number or replace_lines

    2. **replace_lines**: Replaces a specific range of lines in the existing manifest.
       - Requires replace_lines=(start_line, end_line) tuple (1-indexed, inclusive)
       - Use manifest_yaml to provide the replacement content
       - Example: replace_lines=(3, 5) replaces lines 3, 4, and 5
       - Cannot be used with insert_at_line_number

    3. **insert_lines**: Inserts new lines before a specific line number.
       - Requires insert_at_line_number (1-indexed)
       - Use manifest_yaml to provide the content to insert
       - Valid range: 1 to num_lines+1 (num_lines+1 appends at end)
       - Example: insert_at_line_number=1 inserts at the beginning
       - Cannot be used with replace_lines

    Args:
        ctx: FastMCP context (automatically injected in MCP tool calls)
        mode: Edit mode ('replace_all', 'replace_lines', or 'insert_lines')
        manifest_yaml: Content to save, insert, or use for replacement
        insert_at_line_number: Line number to insert before (for insert_lines mode only)
        replace_lines: (start_line, end_line) tuple for replacement (for replace_lines mode only)

    Returns:
        Success message with the file path, or error message if validation fails

    Examples:
        - Replace entire manifest: mode='replace_all', manifest_yaml='<full yaml>'
        - Clear manifest: mode='replace_all', manifest_yaml=''
        - Replace lines 10-15: mode='replace_lines', replace_lines=(10, 15), manifest_yaml='<replacement>'
        - Insert at line 5: mode='insert_lines', insert_at_line_number=5, manifest_yaml='<new lines>'
        - Append at end: mode='insert_lines', insert_at_line_number=<num_lines+1>, manifest_yaml='<new lines>'
    """
    logger.info(f"Setting session manifest with mode={mode}")

    session_id = ctx.session_id

    # Get existing content (empty string if no manifest exists)
    existing_content = get_session_manifest_content(session_id) or ""

    result = _apply_text_edit(
        existing=existing_content,
        mode=mode,
        manifest_yaml=manifest_yaml,
        insert_at_line_number=insert_at_line_number,
        replace_lines=replace_lines,
    )

    if isinstance(result, tuple) and result[0] == "ERROR":
        return result[1]

    assert isinstance(result, str)
    manifest_path = set_session_manifest_content(result, session_id=session_id)

    return f"Successfully saved manifest to session '{session_id}' at: {manifest_path.resolve()}"


@mcp_tool(ToolDomain.MANIFEST_EDITS, read_only=True, idempotent=True, open_world=False)
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
    register_tools(app, ToolDomain.MANIFEST_EDITS)
