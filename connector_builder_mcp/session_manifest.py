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
    MCP_SERVER_NAME,
    SESSION_BASE_DIR,
)
from connector_builder_mcp.mcp_capabilities import mcp_resource


logger = logging.getLogger(__name__)


class SetManifestContentsResult(BaseModel):
    """Result of setting session manifest text."""

    message: str
    revision_id: tuple[int, int, str] | None = None  # (ordinal, timestamp_ns, content_hash)
    diff_summary: str | None = None
    validation_warnings: list[str] = []
    error: str | None = None


def resolve_session_manifest_path(session_id: str) -> Path:
    """Resolve the session manifest path.

    This is a thin wrapper around get_session_dir() for compatibility.
    Returns the manifest.yaml path within the session directory.

    Args:
        session_id: Session ID

    Returns:
        Path to the manifest file
    """
    return get_session_dir(session_id) / "manifest.yaml"


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

    Args:
        session_id: Session ID

    Returns:
        Path to the manifest.yaml file for the session
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
) -> tuple[Path, tuple[int, int, str]]:
    """Set the content of the session manifest file.

    Returns:
        Tuple of (path to written manifest file, revision ID triple)

    Raises:
        Exception: If writing the file fails
    """
    from connector_builder_mcp.manifest_history import save_manifest_revision

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
        _, revision_id = set_session_manifest_content(new_content, session_id=session_id)

        if new_content.strip():
            _, errors, warnings, _ = validate_manifest_content(new_content)
            validation_warnings = [f"ERROR: {e}" for e in errors] + warnings
        else:
            validation_warnings = ["WARNING: Manifest is empty"]

        return SetManifestContentsResult(
            message="Saved manifest",
            revision_id=revision_id,
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
        _, revision_id = set_session_manifest_content(new_content, session_id=session_id)

        if new_content.strip():
            _, errors, warnings, _ = validate_manifest_content(new_content)
            validation_warnings = [f"ERROR: {e}" for e in errors] + warnings
        else:
            validation_warnings = ["WARNING: Manifest is empty"]

        return SetManifestContentsResult(
            message="Saved manifest",
            revision_id=revision_id,
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
        _, revision_id = set_session_manifest_content(new_content, session_id=session_id)

        if new_content.strip():
            _, errors, warnings, _ = validate_manifest_content(new_content)
            validation_warnings = [f"ERROR: {e}" for e in errors] + warnings
        else:
            validation_warnings = ["WARNING: Manifest is empty"]

        return SetManifestContentsResult(
            message="Saved manifest",
            revision_id=revision_id,
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
            replace_all_occurrences=replace_all_occurrences,
        )

        if error:
            return SetManifestContentsResult(message="", error=error)

        diff_summary = unified_diff_with_context(existing_content, new_content, context=2)

        # Write new content
        _, revision_id = set_session_manifest_content(new_content, session_id=session_id)

        if new_content.strip():
            _, errors, warnings, _ = validate_manifest_content(new_content)
            validation_warnings = [f"ERROR: {e}" for e in errors] + warnings
        else:
            validation_warnings = ["WARNING: Manifest is empty"]

        return SetManifestContentsResult(
            message=f"Saved manifest (replaced {success_msg})",
            revision_id=revision_id,
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
