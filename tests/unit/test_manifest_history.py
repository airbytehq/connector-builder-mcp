"""Tests for manifest history tracking functionality."""

import pytest

from connector_builder_mcp.manifest_history import (
    CheckpointType,
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


@pytest.mark.parametrize(
    "manifests,expected_versions",
    [
        ([VALID_MINIMAL_MANIFEST_V1], 1),
        ([VALID_MINIMAL_MANIFEST_V1, VALID_MINIMAL_MANIFEST_V2], 2),
        ([VALID_MINIMAL_MANIFEST_V1, VALID_MINIMAL_MANIFEST_V2, VALID_MINIMAL_MANIFEST_V1], 3),
    ],
)
def test_save_and_get_versions(ctx, manifests, expected_versions):
    """Test saving and retrieving manifest versions."""
    session_id = ctx.session_id

    for i, manifest in enumerate(manifests, 1):
        version_num = save_manifest_version(session_id=session_id, content=manifest)
        assert version_num == i

    history = list_manifest_versions(session_id)
    assert history.total_versions == expected_versions

    for i in range(1, expected_versions + 1):
        version = get_manifest_version(session_id, i)
        assert version is not None
        assert version.content == manifests[i - 1]
        assert version.metadata.version_number == i


@pytest.mark.parametrize(
    "checkpoint_type,checkpoint_details",
    [
        (CheckpointType.VALIDATION_PASS, {"error_count": 0, "warning_count": 0}),
        (CheckpointType.VALIDATION_FAIL, {"error_count": 3, "warning_count": 1}),
        (CheckpointType.READINESS_PASS, {"streams_tested": 2, "streams_successful": 2}),
        (CheckpointType.READINESS_FAIL, {"streams_tested": 2, "streams_successful": 1}),
    ],
)
def test_checkpoint_updates_latest_version(ctx, checkpoint_type, checkpoint_details):
    """Test that checkpointing updates the most recent version's metadata."""
    session_id = ctx.session_id

    save_manifest_version(session_id=session_id, content=VALID_MINIMAL_MANIFEST_V1)

    checkpoint_version = checkpoint_manifest_version(
        session_id=session_id,
        checkpoint_type=checkpoint_type,
        checkpoint_details=checkpoint_details,
    )

    assert checkpoint_version == 1

    version = get_manifest_version(session_id, 1)
    assert version is not None
    assert version.metadata.checkpoint_type == checkpoint_type
    assert version.metadata.checkpoint_details == checkpoint_details


def test_diff_versions_shows_changes(ctx):
    """Test that diff shows changes between versions."""
    session_id = ctx.session_id

    save_manifest_version(session_id=session_id, content=VALID_MINIMAL_MANIFEST_V1)
    save_manifest_version(session_id=session_id, content=VALID_MINIMAL_MANIFEST_V2)

    diff_result = diff_manifest_versions(session_id, 1, 2)

    assert diff_result is not None
    assert "posts" in diff_result.diff
    assert diff_result.from_version == 1
    assert diff_result.to_version == 2


def test_restore_creates_single_version(ctx):
    """Test that restoring a version creates exactly one new version."""
    session_id = ctx.session_id

    save_manifest_version(session_id=session_id, content=VALID_MINIMAL_MANIFEST_V1)
    set_session_manifest_text(ctx, mode="replace_all", new_text=VALID_MINIMAL_MANIFEST_V2)

    restore_session_manifest_version(ctx, version_number=1)

    history = list_manifest_versions(session_id)
    assert history.total_versions == 3

    restored_version = get_manifest_version(session_id, 3)
    assert restored_version is not None
    assert restored_version.content == VALID_MINIMAL_MANIFEST_V1
    assert restored_version.metadata.checkpoint_details == {"restored_from_version": 1}

    current_content = get_session_manifest_content(session_id)
    assert current_content == VALID_MINIMAL_MANIFEST_V1


def test_mcp_tools_smoke(ctx):
    """Smoke test covering list/get/diff/restore MCP tools in one flow."""
    session_id = ctx.session_id

    save_manifest_version(session_id=session_id, content=VALID_MINIMAL_MANIFEST_V1)
    save_manifest_version(session_id=session_id, content=VALID_MINIMAL_MANIFEST_V2)

    history = list_session_manifest_versions(ctx)
    assert history.total_versions == 2

    content = get_session_manifest_version(ctx, version_number=1)
    assert content == VALID_MINIMAL_MANIFEST_V1

    diff = diff_session_manifest_versions(ctx, from_version=1, to_version=2)
    assert "posts" in diff

    result = restore_session_manifest_version(ctx, version_number=1)
    assert "Successfully restored" in result
    assert "version 3" in result
