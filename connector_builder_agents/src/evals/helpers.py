# Copyright (c) 2025 Airbyte, Inc., all rights reserved.


def get_artifact(workspace_dir, artifact_name: str, logger) -> str | None:
    """Read an artifact file from the workspace directory."""
    artifact_path = workspace_dir / artifact_name
    if artifact_path.exists():
        content = artifact_path.read_text(encoding="utf-8")
        logger.info(f"Found {artifact_name} ({len(content)} characters)")
        return content
    else:
        logger.warning(f"No {artifact_name} found")
        return None
