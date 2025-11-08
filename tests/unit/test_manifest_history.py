"""Tests for manifest history tracking functionality."""

import pytest

from connector_builder_mcp.manifest_history import (
    CheckpointType,
    ReadinessCheckpointDetails,
    RestoreCheckpointDetails,
    ValidationCheckpointDetails,
    checkpoint_manifest_revision,
    diff_manifest_revisions,
    diff_session_manifest_versions,
    get_manifest_revision,
    get_session_manifest_version,
    list_manifest_revisions,
    list_session_manifest_versions,
    restore_session_manifest_version,
    save_manifest_revision,
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
    """Test saving and retrieving manifest revisions."""
    session_id = ctx.session_id

    for i, manifest in enumerate(manifests, 1):
        revision_id = save_manifest_revision(session_id=session_id, content=manifest)
        ordinal, _, _ = revision_id
        assert ordinal == i

    history = list_manifest_revisions(session_id)
    assert len(history) == expected_versions

    for i in range(1, expected_versions + 1):
        revision = get_manifest_revision(session_id, i)
        assert revision is not None
        assert revision.content == manifests[i - 1]
        assert revision.metadata.ordinal == i


@pytest.mark.parametrize(
    "checkpoint_type,checkpoint_details",
    [
        (
            CheckpointType.VALIDATION_PASS,
            ValidationCheckpointDetails(error_count=0, warning_count=0),
        ),
        (
            CheckpointType.VALIDATION_FAIL,
            ValidationCheckpointDetails(error_count=3, warning_count=1),
        ),
        (
            CheckpointType.READINESS_PASS,
            ReadinessCheckpointDetails(streams_tested=2, streams_successful=2, total_records=100),
        ),
        (
            CheckpointType.READINESS_FAIL,
            ReadinessCheckpointDetails(streams_tested=2, streams_successful=1, total_records=50),
        ),
    ],
)
def test_checkpoint_updates_latest_version(ctx, checkpoint_type, checkpoint_details):
    """Test that checkpointing updates the most recent revision's metadata."""
    session_id = ctx.session_id

    save_manifest_revision(session_id=session_id, content=VALID_MINIMAL_MANIFEST_V1)

    checkpoint_revision_id = checkpoint_manifest_revision(
        session_id=session_id,
        checkpoint_type=checkpoint_type,
        checkpoint_details=checkpoint_details,
    )

    ordinal, _, _ = checkpoint_revision_id
    assert ordinal == 1

    revision = get_manifest_revision(session_id, 1)
    assert revision is not None
    assert revision.metadata.checkpoint_type == checkpoint_type
    assert revision.metadata.checkpoint_details == checkpoint_details


def test_diff_versions_shows_changes(ctx):
    """Test that diff shows changes between revisions."""
    session_id = ctx.session_id

    save_manifest_revision(session_id=session_id, content=VALID_MINIMAL_MANIFEST_V1)
    save_manifest_revision(session_id=session_id, content=VALID_MINIMAL_MANIFEST_V2)

    diff_result = diff_manifest_revisions(session_id, 1, 2)

    assert diff_result is not None
    assert "posts" in diff_result.diff
    assert diff_result.from_revision[0] == 1  # ordinal
    assert diff_result.to_revision[0] == 2  # ordinal


def test_restore_creates_single_version(ctx):
    """Test that restoring a revision creates exactly one new revision."""
    session_id = ctx.session_id

    revision_id_1 = save_manifest_revision(session_id=session_id, content=VALID_MINIMAL_MANIFEST_V1)
    set_session_manifest_text(ctx, mode="replace_all", new_text=VALID_MINIMAL_MANIFEST_V2)

    restore_session_manifest_version(ctx, version_number=1)

    history = list_manifest_revisions(session_id)
    assert len(history) == 3

    restored_revision = get_manifest_revision(session_id, 3)
    assert restored_revision is not None
    assert restored_revision.content == VALID_MINIMAL_MANIFEST_V1
    assert isinstance(restored_revision.metadata.checkpoint_details, RestoreCheckpointDetails)
    assert restored_revision.metadata.checkpoint_details.restored_from_revision == revision_id_1
    assert restored_revision.metadata.checkpoint_details.restored_from_ordinal == 1

    current_content = get_session_manifest_content(session_id)
    assert current_content == VALID_MINIMAL_MANIFEST_V1


def test_mcp_tools_smoke(ctx):
    """Smoke test covering list/get/diff/restore MCP tools in one flow."""
    session_id = ctx.session_id

    save_manifest_revision(session_id=session_id, content=VALID_MINIMAL_MANIFEST_V1)
    save_manifest_revision(session_id=session_id, content=VALID_MINIMAL_MANIFEST_V2)

    history = list_session_manifest_versions(ctx)
    assert len(history) == 2

    content = get_session_manifest_version(ctx, version_number=1)
    assert content == VALID_MINIMAL_MANIFEST_V1

    diff = diff_session_manifest_versions(ctx, from_version=1, to_version=2)
    assert "posts" in diff

    result = restore_session_manifest_version(ctx, version_number=1)
    assert "Successfully restored" in result
    assert "revision 3" in result
