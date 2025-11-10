"""Manifest revision history tracking for the Connector Builder MCP server.

This module provides revision history management for connector manifests,
including automatic versioning on updates, checkpointing on test results,
revision recall, and diff generation between revisions.

Revisions are identified by a triple: (ordinal, timestamp_ns, content_hash)
- ordinal: Sequential number (1, 2, 3...) for human-friendliness
- timestamp_ns: Nanosecond-precision monotonic timestamp
- content_hash: First 16 chars of SHA-256 hash

Users can reference revisions by any component or combination thereof.
"""

import json
import logging
import time
from datetime import datetime, timezone
from enum import Enum
from typing import Annotated

from fastmcp import FastMCP
from pydantic import BaseModel, ConfigDict, Field

from connector_builder_mcp._manifest_history_utils import (
    _compute_content_hash,
    _get_next_ordinal,
    _load_revision_metadata,
    _save_revision_metadata,
    get_history_dir,
)
from connector_builder_mcp._paths import get_session_manifest_path
from connector_builder_mcp._text_utils import unified_diff_with_context
from connector_builder_mcp.mcp._mcp_utils import ToolDomain, mcp_tool, register_tools


# Type aliases for revision identification
RevisionId = tuple[int, int, str]  # (ordinal, timestamp_ns, content_hash)
RevisionRef = int | str | RevisionId  # Flexible reference type for lookups


class AmbiguousHashError(ValueError):
    """Raised when a hash prefix matches multiple revisions.

    Similar to Git's behavior when an abbreviated commit SHA is ambiguous.
    """

    def __init__(self, hash_prefix: str, matches: list[RevisionId]):
        self.hash_prefix = hash_prefix
        self.matches = matches
        match_strs = "\n".join(f"  - {m}" for m in matches)
        super().__init__(
            f"Ambiguous hash prefix '{hash_prefix}' matches {len(matches)} revisions:\n"
            f"{match_strs}\n"
            f"Please provide more characters to disambiguate."
        )


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

    restored_from_revision: RevisionId  # Full triple of restored revision
    restored_from_ordinal: int  # For backwards compatibility/readability


CheckpointDetails = (
    ValidationCheckpointDetails | ReadinessCheckpointDetails | RestoreCheckpointDetails
)


class ManifestRevisionMetadata(BaseModel):
    """Metadata for a manifest revision.

    Revisions are identified by (ordinal, timestamp_ns, content_hash) triple.
    """

    revision_id: RevisionId  # Full triple: (ordinal, timestamp_ns, content_hash)
    ordinal: int  # Sequential number (1, 2, 3...)
    timestamp_ns: int  # Nanosecond-precision timestamp
    timestamp: float  # Backwards compatibility (seconds since epoch)
    timestamp_iso: str  # ISO 8601 format
    content_hash: str  # First 16 chars of SHA-256
    checkpoint_type: CheckpointType = CheckpointType.NONE
    checkpoint_details: CheckpointDetails | None = None
    file_size_bytes: int


class ManifestRevision(BaseModel):
    """A manifest revision with content and metadata."""

    metadata: ManifestRevisionMetadata
    content: str


class ManifestRevisionSummary(BaseModel):
    """Summary of a manifest revision (without full content)."""

    revision_id: RevisionId  # Full triple
    ordinal: int  # For backwards compatibility
    timestamp_iso: str
    checkpoint_type: CheckpointType
    checkpoint_summary: str | None = None
    content_hash: str  # First 16 chars
    file_size_bytes: int


class ManifestRevisionDiff(BaseModel):
    """Result of comparing two manifest revisions."""

    from_revision: RevisionId  # Full triple
    to_revision: RevisionId  # Full triple
    diff: str
    from_timestamp_iso: str
    to_timestamp_iso: str


# Revision Resolution Functions


def find_revision_by_ordinal(session_id: str, ordinal: int) -> RevisionId | None:
    """Find revision by ordinal number.

    Args:
        session_id: Session ID
        ordinal: Ordinal number (1-indexed)

    Returns:
        Full RevisionId triple, or None if not found
    """
    manifest_path = get_session_manifest_path(session_id)
    history_dir = get_history_dir(manifest_path)
    revision_files = list(history_dir.glob(f"{ordinal}_*.yaml"))

    if not revision_files:
        return None

    # Get the most recent file if multiple exist (shouldn't happen)
    revision_path = max(revision_files, key=lambda p: p.stat().st_mtime)

    # Parse filename: {ordinal}_{timestamp_ns}_{hash}.yaml
    parts = revision_path.stem.split("_")
    if len(parts) >= 3:
        timestamp_ns = int(parts[1])
        content_hash = parts[2]
        return (ordinal, timestamp_ns, content_hash)

    return None


def find_revision_by_hash_prefix(
    session_id: str,
    hash_prefix: str,
    min_length: int = 4,
) -> RevisionId:
    """Find revision by hash prefix (Git-style).

    Args:
        session_id: Session ID
        hash_prefix: Partial hash (min 4 chars)
        min_length: Minimum prefix length (default: 4)

    Returns:
        Full RevisionId triple

    Raises:
        ValueError: If hash_prefix < min_length or no matches
        AmbiguousHashError: If multiple matches found
    """
    if len(hash_prefix) < min_length:
        raise ValueError(
            f"Hash prefix must be at least {min_length} characters, got {len(hash_prefix)}"
        )

    manifest_path = get_session_manifest_path(session_id)
    history_dir = get_history_dir(manifest_path)
    revision_files = list(history_dir.glob("*.yaml"))

    matches: list[RevisionId] = []
    prefix_lower = hash_prefix.lower()

    for revision_file in revision_files:
        parts = revision_file.stem.split("_")
        if len(parts) >= 3:
            ordinal = int(parts[0])
            timestamp_ns = int(parts[1])
            content_hash = parts[2]

            if content_hash.lower().startswith(prefix_lower):
                matches.append((ordinal, timestamp_ns, content_hash))

    if len(matches) == 0:
        raise ValueError(f"No revision found with hash prefix '{hash_prefix}'")

    if len(matches) > 1:
        raise AmbiguousHashError(hash_prefix, matches)

    return matches[0]


def find_revision_by_timestamp(session_id: str, timestamp_ns: int) -> RevisionId | None:
    """Find revision by nanosecond timestamp.

    If multiple revisions share the same timestamp (rare), returns the one with
    highest ordinal.

    Args:
        session_id: Session ID
        timestamp_ns: Nanosecond timestamp

    Returns:
        Full RevisionId triple, or None if not found
    """
    manifest_path = get_session_manifest_path(session_id)
    history_dir = get_history_dir(manifest_path)
    revision_files = list(history_dir.glob(f"*_{timestamp_ns}_*.yaml"))

    if not revision_files:
        return None

    # Parse all matching files and return highest ordinal (collision handling)
    matches: list[RevisionId] = []
    for revision_file in revision_files:
        parts = revision_file.stem.split("_")
        if len(parts) >= 3:
            ordinal = int(parts[0])
            content_hash = parts[2]
            matches.append((ordinal, timestamp_ns, content_hash))

    if not matches:
        return None

    # Return highest ordinal in case of timestamp collision
    return max(matches, key=lambda r: r[0])


def get_latest_revision(session_id: str) -> RevisionId | None:
    """Get the most recent revision.

    Args:
        session_id: Session ID

    Returns:
        Full RevisionId triple, or None if no revisions exist
    """
    revisions = list_manifest_revisions(session_id)

    if len(revisions) == 0:
        return None

    # Get the last revision (highest ordinal)
    latest = revisions[-1]
    return latest.revision_id


def resolve_revision_ref(
    session_id: str,
    ref: RevisionRef,
) -> RevisionId:
    """Resolve any revision reference to full RevisionId triple.

    Accepts:
    - int: ordinal (e.g., 3)
    - str: hash prefix (e.g., "a3f2c"), timestamp (e.g., "1734564789123456789"),
           or special refs ("latest", "HEAD", "@")
    - tuple: full RevisionId triple

    Args:
        session_id: Session ID
        ref: Revision reference in any supported format

    Returns:
        Full RevisionId triple: (ordinal, timestamp_ns, content_hash)

    Raises:
        ValueError: If reference is invalid or not found
        AmbiguousHashError: If hash prefix matches multiple revisions
        TypeError: If reference type is not supported
    """
    # Full tuple - validate and return
    if isinstance(ref, tuple):
        if (
            len(ref) == 3
            and isinstance(ref[0], int)
            and isinstance(ref[1], int)
            and isinstance(ref[2], str)
        ):
            return ref
        raise ValueError(f"Invalid revision tuple: {ref}. Expected (int, int, str)")

    # Integer ordinal
    if isinstance(ref, int):
        revision_id = find_revision_by_ordinal(session_id, ref)
        if revision_id is None:
            raise ValueError(f"Revision with ordinal {ref} not found")
        return revision_id

    # String - could be hash prefix, timestamp, or special ref
    if isinstance(ref, str):
        # Special refs
        if ref.lower() in ("latest", "head", "@"):
            revision_id = get_latest_revision(session_id)
            if revision_id is None:
                raise ValueError("No revisions exist in session")
            return revision_id

        # Timestamp (all digits)
        if ref.isdigit():
            timestamp_ns = int(ref)
            revision_id = find_revision_by_timestamp(session_id, timestamp_ns)
            if revision_id is None:
                raise ValueError(f"Revision with timestamp {timestamp_ns} not found")
            return revision_id

        # Hash prefix (hex characters)
        if all(c in "0123456789abcdefABCDEF" for c in ref):
            return find_revision_by_hash_prefix(session_id, ref)

        raise ValueError(f"Invalid revision reference string: '{ref}'")

    raise TypeError(f"Unsupported reference type: {type(ref)}")


def save_manifest_revision(
    session_id: str,
    content: str,
    checkpoint_type: CheckpointType = CheckpointType.NONE,
    checkpoint_details: CheckpointDetails | None = None,
) -> RevisionId:
    """Save a new revision of the manifest.

    Returns:
        Full RevisionId triple: (ordinal, timestamp_ns, content_hash)
    """
    manifest_path = get_session_manifest_path(session_id)
    history_dir = get_history_dir(manifest_path)
    ordinal = _get_next_ordinal(history_dir)

    # Get nanosecond-precision timestamp
    timestamp = time.time()
    timestamp_ns = int(timestamp * 1_000_000_000)

    # Compute content hash (16 chars)
    content_hash = _compute_content_hash(content, length=16)
    file_size_bytes = len(content.encode("utf-8"))

    # Create full revision ID
    revision_id: RevisionId = (ordinal, timestamp_ns, content_hash)

    # New filename format: {ordinal}_{timestamp_ns}_{hash}.yaml
    revision_path = history_dir / f"{ordinal}_{timestamp_ns}_{content_hash}.yaml"
    revision_path.write_text(content, encoding="utf-8")

    _save_revision_metadata(
        history_dir=history_dir,
        revision_id=revision_id,
        timestamp=timestamp,
        file_size_bytes=file_size_bytes,
        checkpoint_type=checkpoint_type,
        checkpoint_details=checkpoint_details,
    )

    logger.info(
        f"Saved manifest revision {ordinal} ({content_hash[:8]}) for session {session_id[:8]}... "
        f"(checkpoint: {checkpoint_type.value})"
    )

    return revision_id


@mcp_tool(ToolDomain.MANIFEST_EDITS, read_only=True, idempotent=True)
def get_manifest_revision(
    session_id: Annotated[str, Field(description="Session ID")],
    revision: Annotated[
        RevisionRef,
        Field(
            description="Revision reference: int (ordinal), str (hash prefix/timestamp/'latest'), or full tuple"
        ),
    ],
) -> ManifestRevision | None:
    """Get a specific revision of the manifest.

    Accepts flexible reference: int (ordinal), str (hash/timestamp/"latest"), or full tuple.

    Args:
        session_id: Session ID
        revision: Revision reference (ordinal, hash prefix, timestamp, or full tuple)

    Returns:
        Manifest revision with content and metadata, or None if not found
    """
    try:
        revision_id = resolve_revision_ref(session_id, revision)
    except (ValueError, AmbiguousHashError, TypeError):
        return None

    ordinal, timestamp_ns, content_hash = revision_id
    manifest_path = get_session_manifest_path(session_id)
    history_dir = get_history_dir(manifest_path)

    # Look for file with this revision ID
    revision_path = history_dir / f"{ordinal}_{timestamp_ns}_{content_hash}.yaml"

    if not revision_path.exists():
        return None

    content = revision_path.read_text(encoding="utf-8")

    # Load metadata
    metadata_path = revision_path.with_suffix(".meta.json")
    if metadata_path.exists():
        metadata = _load_revision_metadata(metadata_path)
    else:
        # Create metadata from file (for backwards compat or missing metadata)
        timestamp = timestamp_ns / 1_000_000_000
        metadata = ManifestRevisionMetadata(
            revision_id=revision_id,
            ordinal=ordinal,
            timestamp_ns=timestamp_ns,
            timestamp=timestamp,
            timestamp_iso=datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat(),
            content_hash=content_hash,
            checkpoint_type=CheckpointType.NONE,
            checkpoint_details=None,
            file_size_bytes=len(content.encode("utf-8")),
        )

    return ManifestRevision(metadata=metadata, content=content)


@mcp_tool(ToolDomain.MANIFEST_EDITS, read_only=True, idempotent=True)
def list_manifest_revisions(
    session_id: Annotated[str, Field(description="Session ID")],
) -> list[ManifestRevisionSummary]:
    """List all revisions of the manifest for a session.

    Args:
        session_id: Session ID

    Returns:
        List of manifest revision summaries with full RevisionId tuples
    """
    manifest_path = get_session_manifest_path(session_id)
    history_dir = get_history_dir(manifest_path)
    revision_files = sorted(history_dir.glob("*.yaml"), key=lambda p: p.stem)

    revisions: list[ManifestRevisionSummary] = []
    seen_ordinals: set[int] = set()

    for revision_path in revision_files:
        try:
            parts = revision_path.stem.split("_")

            # New format: {ordinal}_{timestamp_ns}_{hash}.yaml
            if len(parts) >= 3:
                ordinal = int(parts[0])
                timestamp_ns = int(parts[1])
                content_hash = parts[2]

                if ordinal in seen_ordinals:
                    continue
                seen_ordinals.add(ordinal)

                revision_id: RevisionId = (ordinal, timestamp_ns, content_hash)

                metadata_path = revision_path.with_suffix(".meta.json")
                if metadata_path.exists():
                    metadata = _load_revision_metadata(metadata_path)
                else:
                    # Create metadata from file
                    timestamp = timestamp_ns / 1_000_000_000
                    content = revision_path.read_text(encoding="utf-8")
                    metadata = ManifestRevisionMetadata(
                        revision_id=revision_id,
                        ordinal=ordinal,
                        timestamp_ns=timestamp_ns,
                        timestamp=timestamp,
                        timestamp_iso=datetime.fromtimestamp(
                            timestamp, tz=timezone.utc
                        ).isoformat(),
                        content_hash=content_hash,
                        checkpoint_type=CheckpointType.NONE,
                        checkpoint_details=None,
                        file_size_bytes=len(content.encode("utf-8")),
                    )

            # Legacy format: v{ordinal}_{timestamp}.yaml
            elif len(parts) >= 2 and parts[0].startswith("v"):
                ordinal = int(parts[0][1:])
                timestamp = float(parts[1])
                timestamp_ns = int(timestamp * 1_000_000_000)

                if ordinal in seen_ordinals:
                    continue
                seen_ordinals.add(ordinal)

                content = revision_path.read_text(encoding="utf-8")
                content_hash = _compute_content_hash(content, length=16)
                revision_id = (ordinal, timestamp_ns, content_hash)

                metadata = ManifestRevisionMetadata(
                    revision_id=revision_id,
                    ordinal=ordinal,
                    timestamp_ns=timestamp_ns,
                    timestamp=timestamp,
                    timestamp_iso=datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat(),
                    content_hash=content_hash,
                    checkpoint_type=CheckpointType.NONE,
                    checkpoint_details=None,
                    file_size_bytes=len(content.encode("utf-8")),
                )
            else:
                continue

            # Build checkpoint summary
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

            summary = ManifestRevisionSummary(
                revision_id=metadata.revision_id,
                ordinal=metadata.ordinal,
                timestamp_iso=metadata.timestamp_iso,
                checkpoint_type=metadata.checkpoint_type,
                checkpoint_summary=checkpoint_summary,
                content_hash=metadata.content_hash,
                file_size_bytes=metadata.file_size_bytes,
            )
            revisions.append(summary)

        except (ValueError, IndexError) as e:
            logger.warning(f"Failed to parse revision file {revision_path}: {e}")
            continue

    revisions.sort(key=lambda r: r.ordinal)

    return revisions


@mcp_tool(ToolDomain.MANIFEST_EDITS, read_only=True, idempotent=True)
def diff_manifest_revisions(
    session_id: Annotated[str, Field(description="Session ID")],
    from_revision: Annotated[
        RevisionRef,
        Field(description="Source revision reference (ordinal, hash prefix, timestamp, or 'latest')"),
    ],
    to_revision: Annotated[
        RevisionRef,
        Field(description="Target revision reference (ordinal, hash prefix, timestamp, or 'latest')"),
    ],
    context_lines: Annotated[int, Field(description="Number of context lines to include in diff")] = 3,
) -> ManifestRevisionDiff | None:
    """Generate a diff between two manifest revisions.

    Accepts flexible references: int (ordinal), str (hash/timestamp/"latest"), or full tuple.

    Args:
        session_id: Session ID
        from_revision: Source revision reference
        to_revision: Target revision reference
        context_lines: Number of context lines to include in diff

    Returns:
        Diff result with full RevisionId tuples, or None if either revision not found
    """
    from_manifest = get_manifest_revision(session_id, from_revision)
    to_manifest = get_manifest_revision(session_id, to_revision)

    if from_manifest is None or to_manifest is None:
        return None

    diff = unified_diff_with_context(
        from_manifest.content,
        to_manifest.content,
        context=context_lines,
    )

    return ManifestRevisionDiff(
        from_revision=from_manifest.metadata.revision_id,
        to_revision=to_manifest.metadata.revision_id,
        diff=diff,
        from_timestamp_iso=from_manifest.metadata.timestamp_iso,
        to_timestamp_iso=to_manifest.metadata.timestamp_iso,
    )


@mcp_tool(ToolDomain.MANIFEST_EDITS, destructive=True)
def checkpoint_manifest_revision(
    session_id: Annotated[str, Field(description="Session ID")],
    checkpoint_type: Annotated[CheckpointType, Field(description="Type of checkpoint to create")],
    checkpoint_details: Annotated[
        CheckpointDetails | None,
        Field(description="Optional checkpoint details (validation/readiness/restore info)"),
    ] = None,
) -> RevisionId | None:
    """Create a checkpoint for the most recent manifest revision.

    This updates the metadata of the most recent revision to mark it as a checkpoint.
    If no revisions exist, returns None.

    Returns:
        Full RevisionId triple of the checkpointed revision, or None if no revisions exist
    """
    history = list_manifest_revisions(session_id)

    if len(history) == 0:
        logger.warning(f"No revisions exist for session {session_id[:8]}... - cannot checkpoint")
        return None

    latest_revision = history[-1]
    ordinal, timestamp_ns, content_hash = latest_revision.revision_id

    manifest_path = get_session_manifest_path(session_id)
    history_dir = get_history_dir(manifest_path)

    # New format: {ordinal}_{timestamp_ns}_{hash}.meta.json
    metadata_path = history_dir / f"{ordinal}_{timestamp_ns}_{content_hash}.meta.json"

    if metadata_path.exists():
        metadata = _load_revision_metadata(metadata_path)
        metadata.checkpoint_type = checkpoint_type
        metadata.checkpoint_details = checkpoint_details

        metadata_path.write_text(
            json.dumps(metadata.model_dump(mode="json"), indent=2), encoding="utf-8"
        )

        logger.info(
            f"Updated checkpoint for revision {ordinal} ({content_hash[:8]}) "
            f"to {checkpoint_type.value}"
        )

    return latest_revision.revision_id



def register_manifest_history_tools(app: FastMCP) -> None:
    """Register manifest history tools with the FastMCP app.

    Args:
        app: FastMCP application instance
    """
    register_tools(app, domain=ToolDomain.MANIFEST_EDITS)

