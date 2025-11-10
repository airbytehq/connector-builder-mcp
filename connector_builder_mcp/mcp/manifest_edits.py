"""MANIFEST_EDITS domain tools - Tools to create, edit, or manage manifests.

This module contains tools for creating, editing, and managing connector manifests.
"""

import logging
import re
from pathlib import Path
from typing import Annotated, Literal

from fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from connector_builder_mcp._guidance import SCAFFOLD_CREATION_SUCCESS_MESSAGE
from connector_builder_mcp._manifest_scaffold_utils import (
    AuthenticationType,
    _generate_manifest_yaml_directly,
)
from connector_builder_mcp._paths import get_session_manifest_path
from connector_builder_mcp._text_utils import (
    insert_text_lines,
    replace_all_text,
    replace_text_content,
    replace_text_lines,
    unified_diff_with_context,
)
from connector_builder_mcp._validation_helpers import validate_manifest_content
from connector_builder_mcp.constants import MCP_SERVER_NAME
from connector_builder_mcp.manifest_history import (
    CheckpointType,
    ManifestRevisionSummary,
    RestoreCheckpointDetails,
    diff_manifest_revisions,
    get_manifest_revision,
    list_manifest_revisions,
    save_manifest_revision,
)
from connector_builder_mcp.mcp._mcp_utils import (
    ToolDomain,
    mcp_resource,
    mcp_tool,
    register_resources,
    register_tools,
)


logger = logging.getLogger(__name__)


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
) -> str:
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
            return "ERROR: mode='replace_all' requires new_text parameter"

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

        ordinal, _, content_hash = revision_id
        result = f"Saved manifest (revision {ordinal}: {content_hash[:8]})"
        if diff_summary:
            result += f"\n\n{diff_summary}"
        if validation_warnings:
            result += f"\n\nValidation warnings:\n" + "\n".join(f"- {w}" for w in validation_warnings)
        return result

    # Get existing content for other modes
    existing_content = get_session_manifest_content(session_id) or ""

    if mode == "replace_lines":
        if replace_lines is None:
            return "ERROR: mode='replace_lines' requires replace_lines=(start,end) tuple"
        if new_text is None:
            return "ERROR: mode='replace_lines' requires new_text parameter"

        start_line, end_line = replace_lines
        new_content, error = replace_text_lines(
            existing_content=existing_content,
            start_line=start_line,
            end_line=end_line,
            replacement_text=new_text,
        )

        if error:
            return f"ERROR: {error}"

        diff_summary = unified_diff_with_context(existing_content, new_content, context=2)

        # Write new content
        _, revision_id = set_session_manifest_content(new_content, session_id=session_id)

        if new_content.strip():
            _, errors, warnings, _ = validate_manifest_content(new_content)
            validation_warnings = [f"ERROR: {e}" for e in errors] + warnings
        else:
            validation_warnings = ["WARNING: Manifest is empty"]

        ordinal, _, content_hash = revision_id
        result = f"Saved manifest (revision {ordinal}: {content_hash[:8]})"
        if diff_summary:
            result += f"\n\n{diff_summary}"
        if validation_warnings:
            result += f"\n\nValidation warnings:\n" + "\n".join(f"- {w}" for w in validation_warnings)
        return result

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
            return f"ERROR: {error}"

        diff_summary = unified_diff_with_context(existing_content, new_content, context=2)

        # Write new content
        _, revision_id = set_session_manifest_content(new_content, session_id=session_id)

        if new_content.strip():
            _, errors, warnings, _ = validate_manifest_content(new_content)
            validation_warnings = [f"ERROR: {e}" for e in errors] + warnings
        else:
            validation_warnings = ["WARNING: Manifest is empty"]

        ordinal, _, content_hash = revision_id
        result = f"Saved manifest (revision {ordinal}: {content_hash[:8]})"
        if diff_summary:
            result += f"\n\n{diff_summary}"
        if validation_warnings:
            result += f"\n\nValidation warnings:\n" + "\n".join(f"- {w}" for w in validation_warnings)
        return result

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
            return f"ERROR: {error}"

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


@mcp_tool(
    ToolDomain.MANIFEST_EDITS,
    read_only=True,
    idempotent=True,
    open_world=False,
)
def get_session_manifest_text(ctx: Context) -> str:
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


@mcp_tool(
    ToolDomain.MANIFEST_EDITS,
    read_only=True,
    idempotent=True,
    open_world=False,
)
def list_session_manifest_versions(ctx: Context) -> list[ManifestRevisionSummary]:
    """List all versions of the manifest for the current session.

    Returns a list of manifest revisions with metadata including revision IDs,
    ordinals, timestamps, checkpoint types, and content hashes. Revisions are
    sorted by ordinal (oldest to newest).

    Args:
        ctx: FastMCP context (automatically injected)

    Returns:
        List of manifest revision summaries
    """
    session_id = ctx.session_id
    return list_manifest_revisions(session_id)


@mcp_tool(
    ToolDomain.MANIFEST_EDITS,
    read_only=True,
    idempotent=True,
    open_world=False,
)
def get_session_manifest_version(
    ctx: Context,
    *,
    version_number: Annotated[
        int,
        Field(description="Version number to retrieve (1-indexed)", ge=1),
    ],
) -> str:
    """Get a specific version of the manifest from history.

    Retrieves the full manifest content for a specific revision by ordinal.
    Use list_session_manifest_versions to see available revisions.

    Args:
        ctx: FastMCP context (automatically injected)
        version_number: Ordinal number to retrieve (1-indexed)

    Returns:
        Manifest YAML content for the specified revision, or error message if not found
    """
    session_id = ctx.session_id
    revision = get_manifest_revision(session_id, version_number)

    if revision is None:
        return f"ERROR: Revision {version_number} not found for session '{session_id}'"

    return revision.content


@mcp_tool(
    ToolDomain.MANIFEST_EDITS,
    read_only=True,
    idempotent=True,
    open_world=False,
)
def diff_session_manifest_versions(
    ctx: Context,
    *,
    from_version: Annotated[
        int,
        Field(description="Source version number for comparison", ge=1),
    ],
    to_version: Annotated[
        int,
        Field(description="Target version number for comparison", ge=1),
    ],
    context_lines: Annotated[
        int,
        Field(description="Number of context lines to include in diff", ge=0, le=10),
    ] = 3,
) -> str:
    """Generate a diff between two manifest revisions.

    Compares two revisions of the manifest and returns a unified diff showing
    the changes between them. Use list_session_manifest_versions to see
    available revisions.

    Args:
        ctx: FastMCP context (automatically injected)
        from_version: Source ordinal number
        to_version: Target ordinal number
        context_lines: Number of context lines to include (default: 3)

    Returns:
        Unified diff between the two revisions, or error message if revisions not found
    """
    session_id = ctx.session_id
    diff_result = diff_manifest_revisions(session_id, from_version, to_version, context_lines)

    if diff_result is None:
        return (
            f"ERROR: Could not generate diff. One or both revisions not found "
            f"(from: {from_version}, to: {to_version})"
        )

    return diff_result.diff


@mcp_tool(
    ToolDomain.MANIFEST_EDITS,
    read_only=False,
    destructive=False,
    idempotent=False,
    open_world=False,
)
def restore_session_manifest_version(
    ctx: Context,
    *,
    version_number: Annotated[
        int,
        Field(description="Version number to restore (1-indexed)", ge=1),
    ],
) -> str:
    """Restore a previous revision of the manifest as the current manifest.

    This retrieves a specific revision from history and sets it as the current
    session manifest. A new revision is automatically created to preserve the
    restore operation in history.

    Returns:
        Success message with revision info, or error message if revision not found
    """

    session_id = ctx.session_id
    revision = get_manifest_revision(session_id, version_number)

    if revision is None:
        return f"ERROR: Revision {version_number} not found for session '{session_id}'"

    manifest_path = get_session_manifest_path(session_id)
    manifest_path.write_text(revision.content, encoding="utf-8")

    new_revision_id = save_manifest_revision(
        session_id=session_id,
        content=revision.content,
        checkpoint_type=CheckpointType.NONE,
        checkpoint_details=RestoreCheckpointDetails(
            restored_from_revision=revision.metadata.revision_id,
            restored_from_ordinal=version_number,
        ),
    )

    new_ordinal, _, new_hash = new_revision_id
    return (
        f"Successfully restored revision {version_number} as current manifest. "
        f"New revision {new_ordinal} ({new_hash[:8]}) created to record this restore operation."
    )


@mcp_tool(
    ToolDomain.MANIFEST_EDITS,
    read_only=False,
    destructive=False,
    idempotent=False,
    open_world=False,
)
def create_connector_manifest_scaffold(
    ctx: Context,
    *,
    connector_name: Annotated[
        str, Field(description="Connector name in kebab-case starting with 'source-'")
    ],
    api_base_url: Annotated[str, Field(description="Base URL for the API")],
    initial_stream_name: Annotated[str, Field(description="Name of the initial stream to create")],
    initial_stream_path: Annotated[
        str, Field(description="API endpoint path for the initial stream")
    ],
    authentication_type: Annotated[
        str,
        Field(
            description="Authentication method (NoAuth, ApiKeyAuthenticator, BearerAuthenticator, BasicHttpAuthenticator, OAuthAuthenticator)"
        ),
    ],
    http_method: Annotated[str, Field(description="HTTP method for requests")] = "GET",
) -> str:
    """Create a basic connector manifest scaffold with the specified configuration.

    This tool generates a complete, valid Airbyte connector manifest YAML file
    with proper authentication, pagination, and stream configuration.

    The generated manifest includes TODO placeholders with inline comments for fields
    that need to be filled in later, ensuring the manifest is valid even in its initial state.

    The generated manifest is automatically saved to the session so other tools can use it
    without needing to pass the manifest content explicitly.

    Tool should only be invoked when setting up the initial connector.
    """
    logger.info(f"Creating connector manifest scaffold for {connector_name}")

    existing_manifest = get_session_manifest_content(ctx.session_id)
    if existing_manifest and existing_manifest.strip():
        return (
            "ERROR: Refusing to overwrite existing session manifest. "
            'To proceed, first call set_session_manifest_text with manifest_yaml="" to reset the session manifest.'
        )

    if not re.match(r"^source-[a-z0-9]+(-[a-z0-9]+)*$", connector_name):
        return "ERROR: Input validation error: Connector name must be in kebab-case starting with 'source-'"

    try:
        auth_type = AuthenticationType(authentication_type)
    except ValueError:
        valid_auth_types = [at.value for at in AuthenticationType]
        return f"ERROR: Input validation error: Invalid authentication_type. Must be one of: {valid_auth_types}"

    manifest_yaml = _generate_manifest_yaml_directly(
        connector_name=connector_name,
        api_base_url=api_base_url,
        initial_stream_name=initial_stream_name,
        initial_stream_path=initial_stream_path,
        authentication_type=auth_type,
        http_method=http_method.upper(),
    )

    from connector_builder_mcp.mcp.manifest_tests import validate_manifest

    validation_result = validate_manifest(ctx, manifest=manifest_yaml)

    if not validation_result.is_valid:
        error_details = "; ".join(validation_result.errors)
        return f"ERROR: Generated manifest failed validation: {error_details}"

    manifest_path, revision_id = set_session_manifest_content(
        manifest_yaml, session_id=ctx.session_id
    )
    ordinal, _, content_hash = revision_id
    logger.info(
        f"Saved generated manifest to session at: {manifest_path} (revision {ordinal}: {content_hash[:8]})"
    )

    success_message = SCAFFOLD_CREATION_SUCCESS_MESSAGE.format(MCP_SERVER_NAME=MCP_SERVER_NAME)
    return f"{success_message}\n\nCreated manifest revision {ordinal} ({content_hash[:8]})."


@mcp_resource(
    uri=f"{MCP_SERVER_NAME}://session/manifest",
    description="Current session's connector manifest YAML content",
    mime_type="text/yaml",
)
def session_manifest_yaml_contents(ctx: Context) -> str:
    """Resource that exposes the current session's manifest file.

    This resource returns the raw YAML manifest content as a string.

    Args:
        ctx: FastMCP context (automatically injected in MCP resource calls)

    Returns:
        The manifest YAML content as a string, or empty string if not found
    """
    session_id = ctx.session_id
    content = get_session_manifest_content(session_id)
    return content or ""


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


def register_session_manifest_tools(app: FastMCP) -> None:
    """Register session manifest tools with the FastMCP app.

    Args:
        app: FastMCP application instance
    """
    register_tools(app, ToolDomain.MANIFEST_EDITS)
    register_resources(app)
