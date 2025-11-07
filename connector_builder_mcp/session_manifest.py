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
from typing import Annotated, Literal

from fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from connector_builder_mcp._text_utils import (
    insert_text_lines,
    replace_text_lines,
    unified_diff_with_context,
)
from connector_builder_mcp._tool_utils import ToolDomain, mcp_tool, register_tools
from connector_builder_mcp._validation_helpers import validate_manifest_content
from connector_builder_mcp.constants import (
    CONNECTOR_BUILDER_MCP_REMOTE_MODE,
    CONNECTOR_BUILDER_MCP_SESSION_DIR,
    CONNECTOR_BUILDER_MCP_SESSION_MANIFEST_PATH,
    CONNECTOR_BUILDER_MCP_SESSION_ROOT,
    CONNECTOR_BUILDER_MCP_SESSIONS_DIR,
    SESSION_BASE_DIR,
)
from connector_builder_mcp.mcp_capabilities import mcp_resource


logger = logging.getLogger(__name__)


class SessionManifestResource(BaseModel):
    """Response model for the session manifest resource."""

    session_id: str
    manifest_path: str
    exists: bool
    content: str


class SetManifestResult(BaseModel):
    """Result of setting session manifest text."""

    message: str
    diff_summary: str | None = None
    validation_warnings: list[str] = []
    error: str | None = None


def _is_remote_mode() -> bool:
    """Check if the server is running in remote mode.

    Returns:
        True if remote mode is active, False otherwise (STDIO mode)
    """
    remote_mode_str = os.environ.get(CONNECTOR_BUILDER_MCP_REMOTE_MODE, "false").lower()
    return remote_mode_str in ("true", "1", "yes")


def _validate_absolute_path(path_str: str, var_name: str) -> Path:
    """Validate that a path string is absolute and return as Path.

    Args:
        path_str: Path string to validate
        var_name: Environment variable name (for error messages)

    Returns:
        Validated absolute Path

    Raises:
        ValueError: If path is not absolute
    """
    path = Path(path_str).expanduser()
    if not path.is_absolute():
        raise ValueError(
            f"{var_name} must be an absolute path, got: {path_str}. "
            f"Relative paths are not allowed for security reasons."
        )
    return path.resolve()


def _check_path_overrides_security() -> None:
    """Check if path overrides are set in remote mode and raise if so.

    Raises:
        RuntimeError: If any path override is set while in remote mode
    """
    if not _is_remote_mode():
        return

    override_vars = [
        CONNECTOR_BUILDER_MCP_SESSION_MANIFEST_PATH,
        CONNECTOR_BUILDER_MCP_SESSION_DIR,
        CONNECTOR_BUILDER_MCP_SESSION_ROOT,
        CONNECTOR_BUILDER_MCP_SESSIONS_DIR,
    ]

    set_overrides = [var for var in override_vars if os.environ.get(var)]

    if set_overrides:
        raise RuntimeError(
            f"Path override environment variables are not allowed in remote mode for security reasons. "
            f"The following variables are set: {', '.join(set_overrides)}. "
            f"Please unset these variables or set {CONNECTOR_BUILDER_MCP_REMOTE_MODE}=false."
        )


def resolve_session_manifest_path(session_id: str) -> Path:
    """Resolve the session manifest path with environment variable overrides.

    This function implements the precedence hierarchy for path overrides:
    1. CONNECTOR_BUILDER_MCP_SESSION_MANIFEST_PATH (most specific)
    2. CONNECTOR_BUILDER_MCP_SESSION_DIR
    3. CONNECTOR_BUILDER_MCP_SESSION_ROOT
    4. CONNECTOR_BUILDER_MCP_SESSIONS_DIR (legacy, deprecated)
    5. Default: ~/.mcp-sessions/{session_id_hash}/manifest.yaml

    Args:
        session_id: Session ID

    Returns:
        Path to the manifest file

    Raises:
        RuntimeError: If path overrides are used in remote mode
        ValueError: If override paths are not absolute
    """
    _check_path_overrides_security()

    manifest_path_override = os.environ.get(CONNECTOR_BUILDER_MCP_SESSION_MANIFEST_PATH)
    if manifest_path_override:
        logger.info(
            f"Using manifest path from {CONNECTOR_BUILDER_MCP_SESSION_MANIFEST_PATH}: {manifest_path_override}"
        )
        if os.environ.get(CONNECTOR_BUILDER_MCP_SESSION_DIR):
            logger.warning(
                f"{CONNECTOR_BUILDER_MCP_SESSION_DIR} is ignored because "
                f"{CONNECTOR_BUILDER_MCP_SESSION_MANIFEST_PATH} is set"
            )
        if os.environ.get(CONNECTOR_BUILDER_MCP_SESSION_ROOT):
            logger.warning(
                f"{CONNECTOR_BUILDER_MCP_SESSION_ROOT} is ignored because "
                f"{CONNECTOR_BUILDER_MCP_SESSION_MANIFEST_PATH} is set"
            )
        if os.environ.get(CONNECTOR_BUILDER_MCP_SESSIONS_DIR):
            logger.warning(
                f"{CONNECTOR_BUILDER_MCP_SESSIONS_DIR} is ignored because "
                f"{CONNECTOR_BUILDER_MCP_SESSION_MANIFEST_PATH} is set"
            )
        return _validate_absolute_path(manifest_path_override, CONNECTOR_BUILDER_MCP_SESSION_MANIFEST_PATH)

    session_dir_override = os.environ.get(CONNECTOR_BUILDER_MCP_SESSION_DIR)
    if session_dir_override:
        logger.info(
            f"Using session directory from {CONNECTOR_BUILDER_MCP_SESSION_DIR}: {session_dir_override}"
        )
        if os.environ.get(CONNECTOR_BUILDER_MCP_SESSION_ROOT):
            logger.warning(
                f"{CONNECTOR_BUILDER_MCP_SESSION_ROOT} is ignored because "
                f"{CONNECTOR_BUILDER_MCP_SESSION_DIR} is set"
            )
        if os.environ.get(CONNECTOR_BUILDER_MCP_SESSIONS_DIR):
            logger.warning(
                f"{CONNECTOR_BUILDER_MCP_SESSIONS_DIR} is ignored because "
                f"{CONNECTOR_BUILDER_MCP_SESSION_DIR} is set"
            )
        session_dir = _validate_absolute_path(session_dir_override, CONNECTOR_BUILDER_MCP_SESSION_DIR)
        return session_dir / "manifest.yaml"

    session_root_override = os.environ.get(CONNECTOR_BUILDER_MCP_SESSION_ROOT)
    if session_root_override:
        logger.info(
            f"Using session root from {CONNECTOR_BUILDER_MCP_SESSION_ROOT}: {session_root_override}"
        )
        if os.environ.get(CONNECTOR_BUILDER_MCP_SESSIONS_DIR):
            logger.warning(
                f"{CONNECTOR_BUILDER_MCP_SESSIONS_DIR} is ignored because "
                f"{CONNECTOR_BUILDER_MCP_SESSION_ROOT} is set"
            )
        session_root = _validate_absolute_path(session_root_override, CONNECTOR_BUILDER_MCP_SESSION_ROOT)
        sanitized_id = _sanitize_session_id(session_id)
        return session_root / sanitized_id / "manifest.yaml"

    sessions_dir_str = os.environ.get(
        CONNECTOR_BUILDER_MCP_SESSIONS_DIR,
        str(Path(tempfile.gettempdir()) / "connector-builder-mcp-sessions"),
    )
    sessions_dir = Path(sessions_dir_str).expanduser().resolve()
    sanitized_id = _sanitize_session_id(session_id)
    return sessions_dir / sanitized_id / "manifest.yaml"


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

    DEPRECATED: This function uses the legacy SESSION_BASE_DIR constant.
    New code should use resolve_session_manifest_path() which respects
    environment variable overrides.

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

    This function uses the centralized path resolver which respects
    environment variable overrides with proper security checks.

    Args:
        session_id: Session ID

    Returns:
        Path to the manifest.yaml file for the session

    Raises:
        RuntimeError: If path overrides are used in remote mode
        ValueError: If override paths are not absolute
    """
    manifest_path = resolve_session_manifest_path(session_id)
    manifest_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    return manifest_path


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
) -> SetManifestResult:
    """Save or edit a connector manifest in the current session.

    This tool supports three modes for updating the session manifest:

    1. **replace_all**: Overwrites the entire manifest file with new content.
       - Use manifest_yaml to provide the full new content
       - To clear the manifest, use mode='replace_all' with manifest_yaml=""
       - Cannot be used with insert_at_line_number or replace_lines
       - Returns diff_summary with line count: "Replaced X lines with Y lines" or "Deleted X lines"

    2. **replace_lines**: Replaces a specific range of lines in the existing manifest.
       - Requires replace_lines=(start_line, end_line) tuple (1-indexed, inclusive)
       - Use manifest_yaml to provide the replacement content
       - Example: replace_lines=(3, 5) replaces lines 3, 4, and 5
       - Cannot be used with insert_at_line_number
       - Returns diff_summary with unified diff

    3. **insert_lines**: Inserts new lines before a specific line number.
       - Requires insert_at_line_number (1-indexed)
       - Use manifest_yaml to provide the content to insert
       - Valid range: 1 to num_lines+1 (num_lines+1 appends at end)
       - Example: insert_at_line_number=1 inserts at the beginning
       - Cannot be used with replace_lines
       - Returns diff_summary with unified diff

    Returns:
        SetManifestResult with message, diff_summary, validation_warnings, and error fields

    Examples:
        - Replace entire manifest: mode='replace_all', manifest_yaml='<full yaml>'
        - Clear manifest: mode='replace_all', manifest_yaml=''
        - Replace lines 10-15: mode='replace_lines', replace_lines=(10, 15), manifest_yaml='<replacement>'
        - Insert at line 5: mode='insert_lines', insert_at_line_number=5, manifest_yaml='<new lines>'
        - Append at end: mode='insert_lines', insert_at_line_number=<num_lines+1>, manifest_yaml='<new lines>'
    """
    logger.info(f"Setting session manifest with mode={mode}")

    session_id = ctx.session_id

    if mode == "replace_all":
        if insert_at_line_number is not None:
            return SetManifestResult(
                message="",
                error="mode='replace_all' cannot be used with insert_at_line_number",
            )
        if replace_lines is not None:
            return SetManifestResult(
                message="",
                error="mode='replace_all' cannot be used with replace_lines",
            )

        old_content = get_session_manifest_content(session_id) or ""
        old_line_count = len(old_content.splitlines())
        new_line_count = len(manifest_yaml.splitlines())

        # Write new content
        set_session_manifest_content(manifest_yaml, session_id=session_id)

        if manifest_yaml == "":
            diff_summary = f"Deleted {old_line_count} lines"
        else:
            diff_summary = f"Replaced {old_line_count} lines with {new_line_count} lines"

        _, errors, warnings, _ = validate_manifest_content(manifest_yaml)
        validation_warnings = [f"ERROR: {e}" for e in errors] + warnings

        return SetManifestResult(
            message="Saved manifest",
            diff_summary=diff_summary,
            validation_warnings=validation_warnings,
        )

    # Get existing content for line-based operations
    existing_content = get_session_manifest_content(session_id) or ""
    lines = existing_content.splitlines(keepends=True)
    num_lines = len(lines)

    if mode == "replace_lines":
        if replace_lines is None:
            return SetManifestResult(
                message="",
                error="mode='replace_lines' requires replace_lines=(start,end) tuple",
            )
        if insert_at_line_number is not None:
            return SetManifestResult(
                message="",
                error="mode='replace_lines' cannot be used with insert_at_line_number",
            )

        start_line, end_line = replace_lines

        if not (1 <= start_line <= end_line):
            return SetManifestResult(
                message="",
                error=f"replace_lines requires 1 <= start_line <= end_line, got start={start_line}, end={end_line}",
            )
        if end_line > num_lines:
            return SetManifestResult(
                message="",
                error=f"replace_lines end_line={end_line} exceeds file length ({num_lines} lines)",
            )

        new_content = replace_text_lines(lines, start_line, end_line, manifest_yaml)

        diff_summary = unified_diff_with_context(existing_content, new_content, context=2)

        # Write new content
        set_session_manifest_content(new_content, session_id=session_id)

        _, errors, warnings, _ = validate_manifest_content(new_content)
        validation_warnings = [f"ERROR: {e}" for e in errors] + warnings

        return SetManifestResult(
            message="Saved manifest",
            diff_summary=diff_summary,
            validation_warnings=validation_warnings,
        )

    if mode == "insert_lines":
        if insert_at_line_number is None:
            return SetManifestResult(
                message="",
                error=f"mode='insert_lines' requires insert_at_line_number (1..{num_lines + 1})",
            )
        if replace_lines is not None:
            return SetManifestResult(
                message="",
                error="mode='insert_lines' cannot be used with replace_lines",
            )

        if not (1 <= insert_at_line_number <= num_lines + 1):
            return SetManifestResult(
                message="",
                error=f"insert_at_line_number must be in range 1..{num_lines + 1}, got {insert_at_line_number}",
            )

        new_content = insert_text_lines(lines, insert_at_line_number, manifest_yaml)

        diff_summary = unified_diff_with_context(existing_content, new_content, context=2)

        # Write new content
        set_session_manifest_content(new_content, session_id=session_id)

        _, errors, warnings, _ = validate_manifest_content(new_content)
        validation_warnings = [f"ERROR: {e}" for e in errors] + warnings

        return SetManifestResult(
            message="Saved manifest",
            diff_summary=diff_summary,
            validation_warnings=validation_warnings,
        )

    return SetManifestResult(
        message="",
        error=f"Unexpected mode: {mode}",
    )


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
