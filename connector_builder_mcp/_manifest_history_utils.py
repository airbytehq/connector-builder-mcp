"""Internal utility functions for manifest history tracking.

This module contains helper functions used by manifest_history.py.
It is kept separate to improve code organization and maintainability.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from connector_builder_mcp.session_manifest import get_session_manifest_path


if TYPE_CHECKING:
    from connector_builder_mcp.manifest_history import (
        CheckpointDetails,
        CheckpointType,
        ManifestVersionMetadata,
    )


def get_history_dir(session_id: str) -> Path:
    """Get the history directory for a session, ensuring it exists.

    Args:
        session_id: Session ID

    Returns:
        Path to the history directory (guaranteed to exist)
    """
    manifest_path = get_session_manifest_path(session_id)
    history_dir = manifest_path.parent / "history"
    history_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    return history_dir


def _compute_content_hash(content: str) -> str:
    """Compute SHA256 hash of content.

    Args:
        content: Content to hash

    Returns:
        Hex digest of SHA256 hash
    """
    import hashlib

    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]


def _get_next_version_number(history_dir: Path) -> int:
    """Get the next version number for a session.

    Args:
        history_dir: History directory path

    Returns:
        Next version number (1-indexed)
    """
    version_files = list(history_dir.glob("*.yaml"))
    if not version_files:
        return 1

    max_version = 0
    for version_file in version_files:
        try:
            parts = version_file.stem.split("_")
            if len(parts) >= 2 and parts[0].startswith("v"):
                version_num = int(parts[0][1:])
                max_version = max(max_version, version_num)
        except (ValueError, IndexError):
            continue

    return max_version + 1


def _save_version_metadata(
    history_dir: Path,
    version_number: int,
    timestamp: float,
    content_hash: str,
    file_size_bytes: int,
    checkpoint_type: "CheckpointType",
    checkpoint_details: "CheckpointDetails | None",
) -> Path:
    """Save version metadata to a JSON file.

    Returns:
        Path to the metadata file
    """
    from connector_builder_mcp.manifest_history import ManifestVersionMetadata

    timestamp_iso = datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()

    metadata = ManifestVersionMetadata(
        version_number=version_number,
        timestamp=timestamp,
        timestamp_iso=timestamp_iso,
        checkpoint_type=checkpoint_type,
        checkpoint_details=checkpoint_details,
        content_hash=content_hash,
        file_size_bytes=file_size_bytes,
    )

    metadata_path = history_dir / f"v{version_number}_{int(timestamp)}.meta.json"
    metadata_path.write_text(
        json.dumps(metadata.model_dump(mode="json"), indent=2), encoding="utf-8"
    )

    return metadata_path


def _load_version_metadata(metadata_path: Path) -> "ManifestVersionMetadata":
    """Load version metadata from a JSON file.

    Args:
        metadata_path: Path to metadata file

    Returns:
        Version metadata
    """
    from connector_builder_mcp.manifest_history import ManifestVersionMetadata

    metadata_dict = json.loads(metadata_path.read_text(encoding="utf-8"))
    return ManifestVersionMetadata(**metadata_dict)
