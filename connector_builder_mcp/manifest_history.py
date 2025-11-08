"""Manifest version history tracking for the Connector Builder MCP server.

This module provides version history management for connector manifests,
including automatic versioning on updates, checkpointing on test results,
version recall, and diff generation between versions.
"""

import json
import logging
import time
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Annotated, Any

from fastmcp import Context
from pydantic import BaseModel, ConfigDict, Field

from connector_builder_mcp._manifest_history_utils import (
    _compute_content_hash,
    _get_next_version_number,
    _load_version_metadata,
    _save_version_metadata,
    get_history_dir,
)
from connector_builder_mcp._text_utils import unified_diff_with_context
from connector_builder_mcp._tool_utils import ToolDomain, mcp_tool
from connector_builder_mcp.session_manifest import get_session_manifest_path


logger = logging.getLogger(__name__)


class CheckpointType(str, Enum):
    """Type of checkpoint for a manifest version."""

    NONE = "none"
    VALIDATION_PASS = "validation_pass"
    VALIDATION_FAIL = "validation_fail"
    TEST_PASS = "test_pass"
    TEST_FAIL = "test_fail"
    READINESS_PASS = "readiness_pass"
    READINESS_FAIL = "readiness_fail"


class ValidationCheckpointDetails(BaseModel):
    """Checkpoint details for manifest validation results."""

    model_config = ConfigDict(extra="ignore")

    error_count: int
    warning_count: int
    errors: list[str] = Field(default_factory=list)


class ReadinessCheckpointDetails(BaseModel):
    """Checkpoint details for connector readiness test results."""

    model_config = ConfigDict(extra="ignore")

    streams_tested: int
    streams_successful: int
    total_records: int


class RestoreCheckpointDetails(BaseModel):
    """Checkpoint details for manifest restore operations."""

    model_config = ConfigDict(extra="ignore")

    restored_from_version: int


CheckpointDetails = (
    ValidationCheckpointDetails | ReadinessCheckpointDetails | RestoreCheckpointDetails
)


class ManifestVersionMetadata(BaseModel):
    """Metadata for a manifest version."""

    version_number: int
    timestamp: float
    timestamp_iso: str
    checkpoint_type: CheckpointType = CheckpointType.NONE
    checkpoint_details: CheckpointDetails | None = None
    content_hash: str
    file_size_bytes: int


class ManifestVersion(BaseModel):
    """A manifest version with content and metadata."""

    metadata: ManifestVersionMetadata
    content: str


class ManifestVersionSummary(BaseModel):
    """Summary of a manifest version (without full content)."""

    version_number: int
    timestamp_iso: str
    checkpoint_type: CheckpointType
    checkpoint_summary: str | None = None
    content_hash: str
    file_size_bytes: int


class ManifestHistoryList(BaseModel):
    """List of manifest versions."""

    total_versions: int
    versions: list[ManifestVersionSummary]


class ManifestDiffResult(BaseModel):
    """Result of comparing two manifest versions."""

    from_version: int
    to_version: int
    diff: str
    from_timestamp_iso: str
    to_timestamp_iso: str


def save_manifest_version(
    session_id: str,
    content: str,
    checkpoint_type: CheckpointType = CheckpointType.NONE,
    checkpoint_details: CheckpointDetails | None = None,
) -> int:
    """Save a new version of the manifest.

    Returns:
        Version number of the saved version
    """
    history_dir = get_history_dir(session_id)
    version_number = _get_next_version_number(history_dir)
    timestamp = time.time()

    version_path = history_dir / f"v{version_number}_{int(timestamp)}.yaml"
    version_path.write_text(content, encoding="utf-8")

    content_hash = _compute_content_hash(content)
    file_size_bytes = len(content.encode("utf-8"))

    _save_version_metadata(
        history_dir=history_dir,
        version_number=version_number,
        timestamp=timestamp,
        content_hash=content_hash,
        file_size_bytes=file_size_bytes,
        checkpoint_type=checkpoint_type,
        checkpoint_details=checkpoint_details,
    )

    logger.info(
        f"Saved manifest version {version_number} for session {session_id[:8]}... "
        f"(checkpoint: {checkpoint_type.value})"
    )

    return version_number


def get_manifest_version(session_id: str, version_number: int) -> ManifestVersion | None:
    """Get a specific version of the manifest.

    Args:
        session_id: Session ID
        version_number: Version number to retrieve

    Returns:
        Manifest version with content and metadata, or None if not found
    """
    history_dir = get_history_dir(session_id)

    version_files = list(history_dir.glob(f"v{version_number}_*.yaml"))
    if not version_files:
        return None

    version_path = max(version_files, key=lambda p: p.stat().st_mtime)

    content = version_path.read_text(encoding="utf-8")

    metadata_path = version_path.with_suffix(".meta.json")
    if not metadata_path.exists():
        timestamp = version_path.stat().st_mtime
        metadata = ManifestVersionMetadata(
            version_number=version_number,
            timestamp=timestamp,
            timestamp_iso=datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat(),
            checkpoint_type=CheckpointType.NONE,
            checkpoint_details=None,
            content_hash=_compute_content_hash(content),
            file_size_bytes=len(content.encode("utf-8")),
        )
    else:
        metadata = _load_version_metadata(metadata_path)

    return ManifestVersion(metadata=metadata, content=content)


def list_manifest_versions(session_id: str) -> ManifestHistoryList:
    """List all versions of the manifest for a session.

    Args:
        session_id: Session ID

    Returns:
        List of manifest version summaries
    """
    history_dir = get_history_dir(session_id)

    version_files = sorted(history_dir.glob("v*.yaml"), key=lambda p: p.stem)

    versions: list[ManifestVersionSummary] = []
    seen_versions: set[int] = set()

    for version_path in version_files:
        try:
            parts = version_path.stem.split("_")
            if len(parts) < 2 or not parts[0].startswith("v"):
                continue

            version_num = int(parts[0][1:])

            if version_num in seen_versions:
                continue
            seen_versions.add(version_num)

            metadata_path = version_path.with_suffix(".meta.json")
            if metadata_path.exists():
                metadata = _load_version_metadata(metadata_path)
            else:
                timestamp = version_path.stat().st_mtime
                content = version_path.read_text(encoding="utf-8")
                metadata = ManifestVersionMetadata(
                    version_number=version_num,
                    timestamp=timestamp,
                    timestamp_iso=datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat(),
                    checkpoint_type=CheckpointType.NONE,
                    checkpoint_details=None,
                    content_hash=_compute_content_hash(content),
                    file_size_bytes=len(content.encode("utf-8")),
                )

            checkpoint_summary = None
            if metadata.checkpoint_type != CheckpointType.NONE:
                checkpoint_summary = metadata.checkpoint_type.value
                if metadata.checkpoint_details:
                    if isinstance(metadata.checkpoint_details, ValidationCheckpointDetails):
                        checkpoint_summary += f" ({metadata.checkpoint_details.error_count} errors)"
                    elif isinstance(metadata.checkpoint_details, ReadinessCheckpointDetails):
                        checkpoint_summary += (
                            f" ({metadata.checkpoint_details.streams_tested} streams)"
                        )

            summary = ManifestVersionSummary(
                version_number=metadata.version_number,
                timestamp_iso=metadata.timestamp_iso,
                checkpoint_type=metadata.checkpoint_type,
                checkpoint_summary=checkpoint_summary,
                content_hash=metadata.content_hash,
                file_size_bytes=metadata.file_size_bytes,
            )
            versions.append(summary)

        except (ValueError, IndexError) as e:
            logger.warning(f"Failed to parse version file {version_path}: {e}")
            continue

    versions.sort(key=lambda v: v.version_number)

    return ManifestHistoryList(total_versions=len(versions), versions=versions)


def diff_manifest_versions(
    session_id: str,
    from_version: int,
    to_version: int,
    context_lines: int = 3,
) -> ManifestDiffResult | None:
    """Generate a diff between two manifest versions.

    Args:
        session_id: Session ID
        from_version: Source version number
        to_version: Target version number
        context_lines: Number of context lines to include in diff

    Returns:
        Diff result, or None if either version not found
    """
    from_manifest = get_manifest_version(session_id, from_version)
    to_manifest = get_manifest_version(session_id, to_version)

    if from_manifest is None or to_manifest is None:
        return None

    diff = unified_diff_with_context(
        from_manifest.content,
        to_manifest.content,
        context=context_lines,
    )

    return ManifestDiffResult(
        from_version=from_version,
        to_version=to_version,
        diff=diff,
        from_timestamp_iso=from_manifest.metadata.timestamp_iso,
        to_timestamp_iso=to_manifest.metadata.timestamp_iso,
    )


def checkpoint_manifest_version(
    session_id: str,
    checkpoint_type: CheckpointType,
    checkpoint_details: CheckpointDetails | None = None,
) -> int | None:
    """Create a checkpoint for the most recent manifest version.

    This updates the metadata of the most recent version to mark it as a checkpoint.
    If no versions exist, returns None.

    Returns:
        Version number of the checkpointed version, or None if no versions exist
    """
    history = list_manifest_versions(session_id)

    if history.total_versions == 0:
        logger.warning(f"No versions exist for session {session_id[:8]}... - cannot checkpoint")
        return None

    latest_version = history.versions[-1]

    history_dir = get_history_dir(session_id)
    metadata_files = list(history_dir.glob(f"v{latest_version.version_number}_*.meta.json"))

    if metadata_files:
        metadata_path = max(metadata_files, key=lambda p: p.stat().st_mtime)
        metadata = _load_version_metadata(metadata_path)

        metadata.checkpoint_type = checkpoint_type
        metadata.checkpoint_details = checkpoint_details

        metadata_path.write_text(
            json.dumps(metadata.model_dump(mode="json"), indent=2), encoding="utf-8"
        )

        logger.info(
            f"Updated checkpoint for version {latest_version.version_number} "
            f"to {checkpoint_type.value}"
        )

    return latest_version.version_number


@mcp_tool(
    ToolDomain.MANIFEST_EDITS,
    read_only=True,
    idempotent=True,
    open_world=False,
)
def list_session_manifest_versions(ctx: Context) -> ManifestHistoryList:
    """List all versions of the manifest for the current session.

    Returns a list of manifest versions with metadata including version numbers,
    timestamps, checkpoint types, and content hashes. Versions are sorted by
    version number (oldest to newest).

    Args:
        ctx: FastMCP context (automatically injected)

    Returns:
        List of manifest version summaries
    """
    session_id = ctx.session_id
    return list_manifest_versions(session_id)


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

    Retrieves the full manifest content for a specific version number.
    Use list_session_manifest_versions to see available versions.

    Args:
        ctx: FastMCP context (automatically injected)
        version_number: Version number to retrieve

    Returns:
        Manifest YAML content for the specified version, or error message if not found
    """
    session_id = ctx.session_id
    version = get_manifest_version(session_id, version_number)

    if version is None:
        return f"ERROR: Version {version_number} not found for session '{session_id}'"

    return version.content


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
    """Generate a diff between two manifest versions.

    Compares two versions of the manifest and returns a unified diff showing
    the changes between them. Use list_session_manifest_versions to see
    available versions.

    Args:
        ctx: FastMCP context (automatically injected)
        from_version: Source version number
        to_version: Target version number
        context_lines: Number of context lines to include (default: 3)

    Returns:
        Unified diff between the two versions, or error message if versions not found
    """
    session_id = ctx.session_id
    diff_result = diff_manifest_versions(session_id, from_version, to_version, context_lines)

    if diff_result is None:
        return (
            f"ERROR: Could not generate diff. One or both versions not found "
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
    """Restore a previous version of the manifest as the current manifest.

    This retrieves a specific version from history and sets it as the current
    session manifest. A new version is automatically created to preserve the
    restore operation in history.

    Returns:
        Success message with version info, or error message if version not found
    """
    from connector_builder_mcp.session_manifest import get_session_manifest_path

    session_id = ctx.session_id
    version = get_manifest_version(session_id, version_number)

    if version is None:
        return f"ERROR: Version {version_number} not found for session '{session_id}'"

    manifest_path = get_session_manifest_path(session_id)
    manifest_path.write_text(version.content, encoding="utf-8")

    new_version = save_manifest_version(
        session_id=session_id,
        content=version.content,
        checkpoint_type=CheckpointType.NONE,
        checkpoint_details=RestoreCheckpointDetails(restored_from_version=version_number),
    )

    return (
        f"Successfully restored version {version_number} as current manifest. "
        f"New version {new_version} created to record this restore operation."
    )
