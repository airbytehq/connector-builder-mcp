"""Internal utility functions for manifest revision history tracking.

This module contains helper functions used by manifest_history.py.
It is kept separate to improve code organization and maintainability.
"""

import hashlib
import json
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field

RevisionId = tuple[int, int, str]  # (ordinal, timestamp_ns, content_hash)

if TYPE_CHECKING:
    pass


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


def get_history_dir(manifest_path: Path) -> Path:
    """Get the history directory for a manifest, ensuring it exists.

    Args:
        manifest_path: Path to the manifest file

    Returns:
        Path to the history directory (guaranteed to exist)
    """
    history_dir = manifest_path.parent / "history"
    history_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    return history_dir


def _compute_content_hash(content: str, length: int = 16) -> str:
    """Compute SHA256 hash of content.

    Args:
        content: Content to hash
        length: Number of hex characters to return (default: 16)

    Returns:
        First `length` characters of SHA256 hex digest
    """
    full_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
    return full_hash[:length]


def _get_next_ordinal(history_dir: Path) -> int:
    """Get the next ordinal number for a revision.

    Args:
        history_dir: History directory path

    Returns:
        Next ordinal number (1-indexed)
    """
    revision_files = list(history_dir.glob("*.yaml"))
    if not revision_files:
        return 1

    max_ordinal = 0
    for revision_file in revision_files:
        try:
            # Parse filename: {ordinal}_{timestamp_ns}_{hash}.yaml
            parts = revision_file.stem.split("_")
            if len(parts) >= 3:
                ordinal = int(parts[0])
                max_ordinal = max(max_ordinal, ordinal)
            # Also support legacy format: v{ordinal}_{timestamp}.yaml
            elif len(parts) >= 2 and parts[0].startswith("v"):
                ordinal = int(parts[0][1:])
                max_ordinal = max(max_ordinal, ordinal)
        except (ValueError, IndexError):
            continue

    return max_ordinal + 1


def _save_revision_metadata(
    history_dir: Path,
    revision_id: "RevisionId",
    timestamp: float,
    file_size_bytes: int,
    checkpoint_type: "CheckpointType",
    checkpoint_details: "CheckpointDetails | None",
) -> Path:
    """Save revision metadata to a JSON file.

    Args:
        history_dir: History directory path
        revision_id: Full revision triple (ordinal, timestamp_ns, content_hash)
        timestamp: Timestamp in seconds (for backwards compat)
        file_size_bytes: Size of manifest content in bytes
        checkpoint_type: Type of checkpoint
        checkpoint_details: Optional checkpoint details

    Returns:
        Path to the metadata file
    """

    ordinal, timestamp_ns, content_hash = revision_id
    timestamp_iso = datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()

    metadata = ManifestRevisionMetadata(
        revision_id=revision_id,
        ordinal=ordinal,
        timestamp_ns=timestamp_ns,
        timestamp=timestamp,
        timestamp_iso=timestamp_iso,
        content_hash=content_hash,
        checkpoint_type=checkpoint_type,
        checkpoint_details=checkpoint_details,
        file_size_bytes=file_size_bytes,
    )

    # New filename format: {ordinal}_{timestamp_ns}_{hash}.meta.json
    metadata_path = history_dir / f"{ordinal}_{timestamp_ns}_{content_hash}.meta.json"
    metadata_path.write_text(
        json.dumps(metadata.model_dump(mode="json"), indent=2), encoding="utf-8"
    )

    return metadata_path


def _load_revision_metadata(metadata_path: Path) -> "ManifestRevisionMetadata":
    """Load revision metadata from a JSON file.

    Args:
        metadata_path: Path to metadata file

    Returns:
        Revision metadata
    """
    metadata_dict = json.loads(metadata_path.read_text(encoding="utf-8"))
    return ManifestRevisionMetadata(**metadata_dict)
