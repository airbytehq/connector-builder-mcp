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
    replace_all_text,
    replace_text_content,
    replace_text_lines,
    unified_diff_with_context,
)
from connector_builder_mcp._tool_utils import ToolDomain, mcp_tool, register_tools
from connector_builder_mcp._validation_helpers import validate_manifest_content
from connector_builder_mcp.constants import (
    CONNECTOR_BUILDER_MCP_SESSION_DIR,
    CONNECTOR_BUILDER_MCP_SESSION_MANIFEST_PATH,
    CONNECTOR_BUILDER_MCP_SESSION_ROOT,
    CONNECTOR_BUILDER_MCP_SESSIONS_DIR,
    MCP_SERVER_NAME,
    SESSION_BASE_DIR,
)
from connector_builder_mcp.mcp_capabilities import mcp_resource


logger = logging.getLogger(__name__)


_TRANSPORT_MODE: str = "unknown"


def set_transport_mode(mode: Literal["stdio", "remote"]) -> None:
    """Set the transport mode for the server.

    This should only be called by the server entrypoint (server.py) based on
    which run method is being used (run_stdio_async vs run_sse/http).

    Args:
        mode: Transport mode - "stdio" for local STDIO, "remote" for SSE/HTTP
    """
    global _TRANSPORT_MODE
    _TRANSPORT_MODE = mode
    logger.info(f"Transport mode set to: {mode}")


class SetManifestContentsResult(BaseModel):
    """Result of setting session manifest text."""

    message: str
    diff_summary: str | None = None
    validation_warnings: list[str] = []
    error: str | None = None


def _is_remote_mode() -> bool:
    """Check if the server is running in remote mode.

    This checks the internal transport mode flag that is set by the server
    entrypoint. It cannot be overridden by users via environment variables.

    Returns:
        True if remote mode is active or unknown (secure-by-default),
        False only if explicitly set to STDIO mode
    """
    return _TRANSPORT_MODE != "stdio"


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

    This function checks the internal transport mode (not user-controllable)
    and rejects path overrides if running in remote mode or if mode is unknown.

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
        mode_desc = "remote mode" if _TRANSPORT_MODE == "remote" else "unknown transport mode"
        raise RuntimeError(
            f"Path override environment variables are not allowed in {mode_desc} for security reasons. "
            f"The following variables are set: {', '.join(set_overrides)}. "
            f"Path overrides are only allowed when running in STDIO mode."
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
        return _validate_absolute_path(
            manifest_path_override, CONNECTOR_BUILDER_MCP_SESSION_MANIFEST_PATH
        )

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
        session_dir = _validate_absolute_path(
            session_dir_override, CONNECTOR_BUILDER_MCP_SESSION_DIR
        )
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
        session_root = _validate_absolute_path(
            session_root_override, CONNECTOR_BUILDER_MCP_SESSION_ROOT
        )
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
        Literal["replace_all", "replace_lines", "insert_lines", "replace_text"],
        Field(
            description="Edit mode: 'replace_all' (overwrite entire file), 'replace_lines' (replace specific line range), 'insert_lines' (insert before specific line), or 'replace_text' (find and replace text content)"
        ),
    ],
    new_text: Annotated[
        str | None,
        Field(
            description="New content for the operation (required for replace_all, replace_lines, and insert_lines modes)"
        ),
    ] = None,
    insert_at_line_number: Annotated[
        int | None,
        Field(
            description="Line number to insert before (1-indexed, required for insert_lines mode)"
        ),
    ] = None,
    replace_lines: Annotated[
        tuple[int, int] | None,
        Field(
            description="(start_line, end_line) tuple for replacement (1-indexed, inclusive, required for replace_lines mode)"
        ),
    ] = None,
    replace_text: Annotated[
        str | None,
        Field(description="Text to find and replace (required for replace_text mode)"),
    ] = None,
    replace_all_occurrences: Annotated[
        bool,
        Field(
            description="Replace all occurrences of text (for replace_text mode). If False, will fail if text appears multiple times."
        ),
    ] = False,
) -> SetManifestContentsResult:
    """Save or edit a connector manifest in the current session.

    This tool supports four modes (line numbering is 1-indexed):

    1. **replace_all**: Overwrites entire file with new content.
       - Requires: new_text (use new_text="" to clear)

    2. **replace_lines**: Replaces specific line range (1-indexed, inclusive).
       - Requires: replace_lines=(start_line, end_line), new_text

    3. **insert_lines**: Inserts new lines before specified line (1-indexed).
       - Requires: insert_at_line_number, new_text
       - Range: 1 to num_lines+1 (num_lines+1 appends at end)

    4. **replace_text**: Find and replace text content.
       - Requires: replace_text, new_text
       - Optional: replace_all_occurrences (default: False)
       - Fails if text appears multiple times unless replace_all_occurrences=True

    Examples:
        mode='replace_lines', replace_lines=(10, 15), new_text='new content'
        mode='insert_lines', insert_at_line_number=5, new_text='new lines'
        mode='replace_text', replace_text='old_value', new_text='new_value'
        mode='replace_text', replace_text='old_value', new_text='new_value', replace_all_occurrences=True
    """
    logger.info(f"Setting session manifest with mode={mode}")

    session_id = ctx.session_id

    if mode == "replace_all":
        if new_text is None:
            return SetManifestContentsResult(
                message="",
                error="mode='replace_all' requires new_text parameter",
            )

        old_content = get_session_manifest_content(session_id) or ""
        new_content, diff_summary = replace_all_text(
            old_content=old_content,
            new_content=new_text,
        )

        # Write new content
        set_session_manifest_content(new_content, session_id=session_id)

        _, errors, warnings, _ = validate_manifest_content(new_content)
        validation_warnings = [f"ERROR: {e}" for e in errors] + warnings

        return SetManifestContentsResult(
            message="Saved manifest",
            diff_summary=diff_summary,
            validation_warnings=validation_warnings,
        )

    # Get existing content for other modes
    existing_content = get_session_manifest_content(session_id) or ""

    if mode == "replace_lines":
        if replace_lines is None:
            return SetManifestContentsResult(
                message="",
                error="mode='replace_lines' requires replace_lines=(start,end) tuple",
            )
        if new_text is None:
            return SetManifestContentsResult(
                message="",
                error="mode='replace_lines' requires new_text parameter",
            )

        start_line, end_line = replace_lines
        new_content, error = replace_text_lines(
            existing_content=existing_content,
            start_line=start_line,
            end_line=end_line,
            replacement_text=new_text,
        )

        if error:
            return SetManifestContentsResult(message="", error=error)

        diff_summary = unified_diff_with_context(existing_content, new_content, context=2)

        # Write new content
        set_session_manifest_content(new_content, session_id=session_id)

        _, errors, warnings, _ = validate_manifest_content(new_content)
        validation_warnings = [f"ERROR: {e}" for e in errors] + warnings

        return SetManifestContentsResult(
            message="Saved manifest",
            diff_summary=diff_summary,
            validation_warnings=validation_warnings,
        )

    if mode == "insert_lines":
        if insert_at_line_number is None:
            return SetManifestContentsResult(
                message="",
                error="mode='insert_lines' requires insert_at_line_number parameter",
            )
        if new_text is None:
            return SetManifestContentsResult(
                message="",
                error="mode='insert_lines' requires new_text parameter",
            )

        new_content, error = insert_text_lines(
            existing_content=existing_content,
            insert_at_line=insert_at_line_number,
            text_to_insert=new_text,
        )

        if error:
            return SetManifestContentsResult(message="", error=error)

        diff_summary = unified_diff_with_context(existing_content, new_content, context=2)

        # Write new content
        set_session_manifest_content(new_content, session_id=session_id)

        _, errors, warnings, _ = validate_manifest_content(new_content)
        validation_warnings = [f"ERROR: {e}" for e in errors] + warnings

        return SetManifestContentsResult(
            message="Saved manifest",
            diff_summary=diff_summary,
            validation_warnings=validation_warnings,
        )

    if mode == "replace_text":
        if replace_text is None:
            return SetManifestContentsResult(
                message="",
                error="mode='replace_text' requires replace_text parameter",
            )
        if new_text is None:
            return SetManifestContentsResult(
                message="",
                error="mode='replace_text' requires new_text parameter",
            )

        new_content, success_msg, error = replace_text_content(
            existing_content=existing_content,
            find_text=replace_text,
            replacement_text=new_text,
            replace_all=replace_all_occurrences,
        )

        if error:
            return SetManifestContentsResult(message="", error=error)

        diff_summary = unified_diff_with_context(existing_content, new_content, context=2)

        # Write new content
        set_session_manifest_content(new_content, session_id=session_id)

        _, errors, warnings, _ = validate_manifest_content(new_content)
        validation_warnings = [f"ERROR: {e}" for e in errors] + warnings

        return SetManifestContentsResult(
            message=f"Saved manifest (replaced {success_msg})",
            diff_summary=diff_summary,
            validation_warnings=validation_warnings,
        )

    return SetManifestContentsResult(
        message="",
        error=f"Unexpected mode: {mode}",
    )


@mcp_tool(ToolDomain.MANIFEST_EDITS, read_only=True, idempotent=True, open_world=False)
def get_session_manifest(ctx: Context) -> str:
    """Get the connector manifest from the current session.

    Note: This tool is provided for backwards compatibility with clients that
    don't support MCP resources. For clients that support MCP resources, prefer
    using the 'session_manifest_yaml_contents' resource for more efficient read access.
    The resource URI should be approximately 'connector-builder-mcp://session/manifest'.
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
