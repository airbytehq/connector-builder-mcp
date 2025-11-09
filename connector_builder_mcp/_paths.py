"""Path utilities for session-based manifest management.

This module provides filesystem path helpers for session directories and manifest files.
Extracted to avoid circular dependencies between session_manifest and manifest_history modules.
"""

import hashlib
from functools import lru_cache
from pathlib import Path

from connector_builder_mcp.constants import SESSION_BASE_DIR


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
