"""Internal utility functions for manifest revision history tracking.

This module contains helper functions used by manifest_history.py.
It is kept separate to improve code organization and maintainability.
"""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from connector_builder_mcp.mcp.manifest_history import (
        CheckpointDetails,
        CheckpointType,
        ManifestRevisionMetadata,
        RevisionId,
    )


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
    from connector_builder_mcp.manifest_history import ManifestRevisionMetadata

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
    from connector_builder_mcp.manifest_history import ManifestRevisionMetadata

    metadata_dict = json.loads(metadata_path.read_text(encoding="utf-8"))
    return ManifestRevisionMetadata(**metadata_dict)
