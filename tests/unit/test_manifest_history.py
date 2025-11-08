"""Tests for manifest history tracking functionality."""

from connector_builder_mcp.manifest_history import (
    CheckpointType,
    ManifestHistoryList,
    ManifestVersion,
    checkpoint_manifest_version,
    diff_manifest_versions,
    diff_session_manifest_versions,
    get_manifest_version,
    get_session_manifest_version,
    list_manifest_versions,
    list_session_manifest_versions,
    restore_session_manifest_version,
    save_manifest_version,
)
from connector_builder_mcp.session_manifest import (
    get_session_manifest_content,
    set_session_manifest_text,
)


VALID_MINIMAL_MANIFEST_V1 = """version: "0.1.0"
type: DeclarativeSource
check:
  type: CheckStream
  stream_names: ["users"]
streams:
  - type: DeclarativeStream
    name: users
    primary_key: ["id"]
    retriever:
      type: SimpleRetriever
      requester:
        type: HttpRequester
        url_base: "https://api.example.com"
        path: "/users"
      record_selector:
        type: RecordSelector
        extractor:
          type: DpathExtractor
          field_path: []
"""

VALID_MINIMAL_MANIFEST_V2 = """version: "0.1.0"
type: DeclarativeSource
check:
  type: CheckStream
  stream_names: ["users", "posts"]
streams:
  - type: DeclarativeStream
    name: users
    primary_key: ["id"]
    retriever:
      type: SimpleRetriever
      requester:
        type: HttpRequester
        url_base: "https://api.example.com"
        path: "/users"
      record_selector:
        type: RecordSelector
        extractor:
          type: DpathExtractor
          field_path: []
  - type: DeclarativeStream
    name: posts
    primary_key: ["id"]
    retriever:
      type: SimpleRetriever
      requester:
        type: HttpRequester
        url_base: "https://api.example.com"
        path: "/posts"
      record_selector:
        type: RecordSelector
        extractor:
          type: DpathExtractor
          field_path: []
"""


def test_save_manifest_version_creates_first_version(ctx) -> None:
    """Test saving the first version of a manifest."""
    session_id = ctx.session_id

    version_num = save_manifest_version(
        session_id=session_id,
        content=VALID_MINIMAL_MANIFEST_V1,
    )

    assert version_num == 1


def test_save_manifest_version_increments_version_number(ctx) -> None:
    """Test that version numbers increment correctly."""
    session_id = ctx.session_id

    version_1 = save_manifest_version(
        session_id=session_id,
        content=VALID_MINIMAL_MANIFEST_V1,
    )
    version_2 = save_manifest_version(
        session_id=session_id,
        content=VALID_MINIMAL_MANIFEST_V2,
    )

    assert version_1 == 1
    assert version_2 == 2


def test_get_manifest_version_retrieves_content(ctx) -> None:
    """Test retrieving a specific version's content."""
    session_id = ctx.session_id

    save_manifest_version(
        session_id=session_id,
        content=VALID_MINIMAL_MANIFEST_V1,
    )

    version = get_manifest_version(session_id, 1)

    assert version is not None
    assert isinstance(version, ManifestVersion)
    assert version.content == VALID_MINIMAL_MANIFEST_V1
    assert version.metadata.version_number == 1
    assert version.metadata.checkpoint_type == CheckpointType.NONE


def test_get_manifest_version_returns_none_for_nonexistent(ctx) -> None:
    """Test that getting a nonexistent version returns None."""
    session_id = ctx.session_id

    version = get_manifest_version(session_id, 999)

    assert version is None


def test_list_manifest_versions_empty(ctx) -> None:
    """Test listing versions when none exist."""
    session_id = ctx.session_id

    history = list_manifest_versions(session_id)

    assert isinstance(history, ManifestHistoryList)
    assert history.total_versions == 0
    assert len(history.versions) == 0


def test_list_manifest_versions_multiple(ctx) -> None:
    """Test listing multiple versions."""
    session_id = ctx.session_id

    save_manifest_version(session_id=session_id, content=VALID_MINIMAL_MANIFEST_V1)
    save_manifest_version(session_id=session_id, content=VALID_MINIMAL_MANIFEST_V2)

    history = list_manifest_versions(session_id)

    assert history.total_versions == 2
    assert len(history.versions) == 2
    assert history.versions[0].version_number == 1
    assert history.versions[1].version_number == 2


def test_checkpoint_manifest_version_creates_checkpoint(ctx) -> None:
    """Test creating a checkpoint for a manifest version."""
    session_id = ctx.session_id

    save_manifest_version(session_id=session_id, content=VALID_MINIMAL_MANIFEST_V1)

    checkpoint_version = checkpoint_manifest_version(
        session_id=session_id,
        checkpoint_type=CheckpointType.VALIDATION_PASS,
        checkpoint_details={"error_count": 0, "warning_count": 0},
    )

    assert checkpoint_version == 1

    version = get_manifest_version(session_id, 1)
    assert version is not None
    assert version.metadata.checkpoint_type == CheckpointType.VALIDATION_PASS
    assert version.metadata.checkpoint_details == {"error_count": 0, "warning_count": 0}


def test_checkpoint_manifest_version_creates_new_version_if_content_changed(ctx) -> None:
    """Test that checkpoint updates the most recent version."""
    session_id = ctx.session_id

    save_manifest_version(session_id=session_id, content=VALID_MINIMAL_MANIFEST_V1)

    set_session_manifest_text(ctx, mode="replace_all", new_text=VALID_MINIMAL_MANIFEST_V2)

    checkpoint_version = checkpoint_manifest_version(
        session_id=session_id,
        checkpoint_type=CheckpointType.VALIDATION_PASS,
        checkpoint_details={"error_count": 0, "warning_count": 0},
    )

    assert checkpoint_version == 2

    version = get_manifest_version(session_id, 2)
    assert version is not None
    assert version.metadata.checkpoint_type == CheckpointType.VALIDATION_PASS
    assert version.content == VALID_MINIMAL_MANIFEST_V2


def test_diff_manifest_versions_shows_changes(ctx) -> None:
    """Test generating diff between two versions."""
    session_id = ctx.session_id

    save_manifest_version(session_id=session_id, content=VALID_MINIMAL_MANIFEST_V1)
    save_manifest_version(session_id=session_id, content=VALID_MINIMAL_MANIFEST_V2)

    diff_result = diff_manifest_versions(session_id, 1, 2)

    assert diff_result is not None
    assert diff_result.from_version == 1
    assert diff_result.to_version == 2
    assert "posts" in diff_result.diff


def test_diff_manifest_versions_returns_none_for_nonexistent(ctx) -> None:
    """Test that diff returns None when version doesn't exist."""
    session_id = ctx.session_id

    save_manifest_version(session_id=session_id, content=VALID_MINIMAL_MANIFEST_V1)

    diff_result = diff_manifest_versions(session_id, 1, 999)

    assert diff_result is None


def test_list_session_manifest_versions_tool(ctx) -> None:
    """Test the list_session_manifest_versions MCP tool."""
    save_manifest_version(session_id=ctx.session_id, content=VALID_MINIMAL_MANIFEST_V1)
    save_manifest_version(session_id=ctx.session_id, content=VALID_MINIMAL_MANIFEST_V2)

    result = list_session_manifest_versions(ctx)

    assert isinstance(result, ManifestHistoryList)
    assert result.total_versions == 2


def test_get_session_manifest_version_tool(ctx) -> None:
    """Test the get_session_manifest_version MCP tool."""
    save_manifest_version(session_id=ctx.session_id, content=VALID_MINIMAL_MANIFEST_V1)

    result = get_session_manifest_version(ctx, version_number=1)

    assert result == VALID_MINIMAL_MANIFEST_V1


def test_get_session_manifest_version_tool_nonexistent(ctx) -> None:
    """Test the get_session_manifest_version MCP tool with nonexistent version."""
    result = get_session_manifest_version(ctx, version_number=999)

    assert "ERROR" in result
    assert "not found" in result


def test_diff_session_manifest_versions_tool(ctx) -> None:
    """Test the diff_session_manifest_versions MCP tool."""
    save_manifest_version(session_id=ctx.session_id, content=VALID_MINIMAL_MANIFEST_V1)
    save_manifest_version(session_id=ctx.session_id, content=VALID_MINIMAL_MANIFEST_V2)

    result = diff_session_manifest_versions(ctx, from_version=1, to_version=2)

    assert "posts" in result


def test_diff_session_manifest_versions_tool_nonexistent(ctx) -> None:
    """Test the diff_session_manifest_versions MCP tool with nonexistent version."""
    save_manifest_version(session_id=ctx.session_id, content=VALID_MINIMAL_MANIFEST_V1)

    result = diff_session_manifest_versions(ctx, from_version=1, to_version=999)

    assert "ERROR" in result
    assert "not found" in result


def test_restore_session_manifest_version_tool(ctx) -> None:
    """Test the restore_session_manifest_version MCP tool."""
    save_manifest_version(session_id=ctx.session_id, content=VALID_MINIMAL_MANIFEST_V1)
    set_session_manifest_text(ctx, mode="replace_all", new_text=VALID_MINIMAL_MANIFEST_V2)

    result = restore_session_manifest_version(ctx, version_number=1)

    assert "Successfully restored" in result

    current_content = get_session_manifest_content(ctx.session_id)
    assert current_content == VALID_MINIMAL_MANIFEST_V1


def test_restore_session_manifest_version_tool_nonexistent(ctx) -> None:
    """Test the restore_session_manifest_version MCP tool with nonexistent version."""
    result = restore_session_manifest_version(ctx, version_number=999)

    assert "ERROR" in result
    assert "not found" in result


def test_set_session_manifest_text_creates_version(ctx) -> None:
    """Test that set_session_manifest_text automatically creates a version."""
    set_session_manifest_text(ctx, mode="replace_all", new_text=VALID_MINIMAL_MANIFEST_V1)

    history = list_manifest_versions(ctx.session_id)

    assert history.total_versions == 1
    assert history.versions[0].version_number == 1


def test_checkpoint_with_validation_pass(ctx) -> None:
    """Test checkpoint with validation pass details."""
    session_id = ctx.session_id

    save_manifest_version(session_id=session_id, content=VALID_MINIMAL_MANIFEST_V1)

    checkpoint_manifest_version(
        session_id=session_id,
        checkpoint_type=CheckpointType.VALIDATION_PASS,
        checkpoint_details={"error_count": 0, "warning_count": 2},
    )

    version = get_manifest_version(session_id, 1)
    assert version is not None
    assert version.metadata.checkpoint_type == CheckpointType.VALIDATION_PASS
    assert version.metadata.checkpoint_details["error_count"] == 0
    assert version.metadata.checkpoint_details["warning_count"] == 2


def test_checkpoint_with_validation_fail(ctx) -> None:
    """Test checkpoint with validation failure details."""
    session_id = ctx.session_id

    save_manifest_version(session_id=session_id, content=VALID_MINIMAL_MANIFEST_V1)

    checkpoint_manifest_version(
        session_id=session_id,
        checkpoint_type=CheckpointType.VALIDATION_FAIL,
        checkpoint_details={
            "error_count": 3,
            "warning_count": 1,
            "errors": ["Error 1", "Error 2", "Error 3"],
        },
    )

    version = get_manifest_version(session_id, 1)
    assert version is not None
    assert version.metadata.checkpoint_type == CheckpointType.VALIDATION_FAIL
    assert version.metadata.checkpoint_details["error_count"] == 3


def test_checkpoint_with_readiness_pass(ctx) -> None:
    """Test checkpoint with readiness test pass details."""
    session_id = ctx.session_id

    save_manifest_version(session_id=session_id, content=VALID_MINIMAL_MANIFEST_V1)

    checkpoint_manifest_version(
        session_id=session_id,
        checkpoint_type=CheckpointType.READINESS_PASS,
        checkpoint_details={
            "streams_tested": 2,
            "streams_successful": 2,
            "total_records": 150,
        },
    )

    version = get_manifest_version(session_id, 1)
    assert version is not None
    assert version.metadata.checkpoint_type == CheckpointType.READINESS_PASS
    assert version.metadata.checkpoint_details["streams_tested"] == 2
    assert version.metadata.checkpoint_details["streams_successful"] == 2


def test_checkpoint_with_readiness_fail(ctx) -> None:
    """Test checkpoint with readiness test failure details."""
    session_id = ctx.session_id

    save_manifest_version(session_id=session_id, content=VALID_MINIMAL_MANIFEST_V1)

    checkpoint_manifest_version(
        session_id=session_id,
        checkpoint_type=CheckpointType.READINESS_FAIL,
        checkpoint_details={
            "streams_tested": 2,
            "streams_successful": 1,
            "total_records": 50,
        },
    )

    version = get_manifest_version(session_id, 1)
    assert version is not None
    assert version.metadata.checkpoint_type == CheckpointType.READINESS_FAIL
    assert version.metadata.checkpoint_details["streams_successful"] == 1


def test_version_metadata_includes_timestamps(ctx) -> None:
    """Test that version metadata includes proper timestamps."""
    session_id = ctx.session_id

    save_manifest_version(session_id=session_id, content=VALID_MINIMAL_MANIFEST_V1)

    version = get_manifest_version(session_id, 1)
    assert version is not None
    assert version.metadata.timestamp > 0
    assert version.metadata.timestamp_iso is not None
    assert "T" in version.metadata.timestamp_iso


def test_version_metadata_includes_content_hash(ctx) -> None:
    """Test that version metadata includes content hash."""
    session_id = ctx.session_id

    save_manifest_version(session_id=session_id, content=VALID_MINIMAL_MANIFEST_V1)

    version = get_manifest_version(session_id, 1)
    assert version is not None
    assert version.metadata.content_hash is not None
    assert len(version.metadata.content_hash) == 16


def test_version_metadata_includes_file_size(ctx) -> None:
    """Test that version metadata includes file size."""
    session_id = ctx.session_id

    save_manifest_version(session_id=session_id, content=VALID_MINIMAL_MANIFEST_V1)

    version = get_manifest_version(session_id, 1)
    assert version is not None
    assert version.metadata.file_size_bytes > 0
    assert version.metadata.file_size_bytes == len(VALID_MINIMAL_MANIFEST_V1.encode("utf-8"))


def test_list_versions_shows_checkpoint_summary(ctx) -> None:
    """Test that list versions shows checkpoint summary."""
    session_id = ctx.session_id

    save_manifest_version(session_id=session_id, content=VALID_MINIMAL_MANIFEST_V1)
    checkpoint_manifest_version(
        session_id=session_id,
        checkpoint_type=CheckpointType.VALIDATION_PASS,
        checkpoint_details={"error_count": 0, "warning_count": 2},
    )

    history = list_manifest_versions(session_id)

    assert history.total_versions == 1
    assert history.versions[0].checkpoint_type == CheckpointType.VALIDATION_PASS
    assert history.versions[0].checkpoint_summary is not None
    assert "validation_pass" in history.versions[0].checkpoint_summary


def test_restore_creates_new_version(ctx) -> None:
    """Test that restoring a version creates a new version."""
    session_id = ctx.session_id

    save_manifest_version(session_id=session_id, content=VALID_MINIMAL_MANIFEST_V1)
    set_session_manifest_text(ctx, mode="replace_all", new_text=VALID_MINIMAL_MANIFEST_V2)

    restore_session_manifest_version(ctx, version_number=1)

    history = list_manifest_versions(session_id)
    assert history.total_versions == 3

    latest_version = get_manifest_version(session_id, 3)
    assert latest_version is not None
    assert latest_version.content == VALID_MINIMAL_MANIFEST_V1
    assert latest_version.metadata.checkpoint_details is not None
    assert latest_version.metadata.checkpoint_details["restored_from_version"] == 1
