"""Tests for set_session_manifest_text tool with all edit modes."""


from connector_builder_mcp.session_manifest import (
    SetManifestContentsResult,
    get_session_manifest_content,
    set_session_manifest_text,
)


VALID_MINIMAL_MANIFEST = """version: "0.1.0"
type: DeclarativeSource
check:
  type: CheckStream
  stream_names: ["test"]
streams:
  - type: DeclarativeStream
    name: test
    primary_key: ["id"]
    retriever:
      type: SimpleRetriever
      requester:
        type: HttpRequester
        url_base: "https://api.example.com"
        path: "/test"
      record_selector:
        type: RecordSelector
        extractor:
          type: DpathExtractor
          field_path: []
"""


def test_replace_all_mode_with_content(ctx) -> None:
    """Test replace_all mode with new content."""
    result = set_session_manifest_text(
        ctx,
        mode="replace_all",
        new_text=VALID_MINIMAL_MANIFEST,
    )

    assert isinstance(result, SetManifestContentsResult)
    assert result.error is None
    assert "Saved manifest" in result.message
    assert "Replaced 0 lines with" in result.diff_summary
    assert isinstance(result.validation_warnings, list)

    content = get_session_manifest_content(ctx.session_id)
    assert content == VALID_MINIMAL_MANIFEST


def test_replace_all_mode_delete_content(ctx) -> None:
    """Test replace_all mode with empty string (delete)."""
    set_session_manifest_text(ctx, mode="replace_all", new_text=VALID_MINIMAL_MANIFEST)

    result = set_session_manifest_text(
        ctx,
        mode="replace_all",
        new_text="",
    )

    assert isinstance(result, SetManifestContentsResult)
    assert result.error is None
    assert "Deleted" in result.diff_summary and "lines" in result.diff_summary
    assert isinstance(result.validation_warnings, list)

    content = get_session_manifest_content(ctx.session_id)
    assert content == ""


def test_replace_all_mode_missing_new_text(ctx) -> None:
    """Test replace_all mode without new_text parameter."""
    result = set_session_manifest_text(
        ctx,
        mode="replace_all",
    )

    assert isinstance(result, SetManifestContentsResult)
    assert result.error is not None
    assert "requires new_text parameter" in result.error


def test_replace_lines_mode_success(ctx) -> None:
    """Test replace_lines mode with valid line range."""
    set_session_manifest_text(ctx, mode="replace_all", new_text=VALID_MINIMAL_MANIFEST)

    result = set_session_manifest_text(
        ctx,
        mode="replace_lines",
        replace_lines=(2, 2),
        new_text="# Modified line\n",
    )

    assert isinstance(result, SetManifestContentsResult)
    assert result.error is None
    assert "Saved manifest" in result.message
    assert result.diff_summary is not None
    assert result.diff_summary != "[no changes]"

    content = get_session_manifest_content(ctx.session_id)
    assert "# Modified line" in content


def test_replace_lines_mode_no_changes(ctx) -> None:
    """Test replace_lines mode where content doesn't actually change."""
    set_session_manifest_text(ctx, mode="replace_all", new_text=VALID_MINIMAL_MANIFEST)

    lines = VALID_MINIMAL_MANIFEST.splitlines(keepends=True)
    result = set_session_manifest_text(
        ctx,
        mode="replace_lines",
        replace_lines=(2, 2),
        new_text=lines[1],
    )

    assert isinstance(result, SetManifestContentsResult)
    assert result.error is None
    assert result.diff_summary == "[no changes]"


def test_replace_lines_mode_missing_params(ctx) -> None:
    """Test replace_lines mode with missing parameters."""
    set_session_manifest_text(ctx, mode="replace_all", new_text=VALID_MINIMAL_MANIFEST)

    result = set_session_manifest_text(
        ctx,
        mode="replace_lines",
        new_text="replacement\n",
    )

    assert isinstance(result, SetManifestContentsResult)
    assert result.error is not None
    assert "requires replace_lines" in result.error


def test_replace_lines_mode_out_of_range(ctx) -> None:
    """Test replace_lines mode with out-of-range line numbers."""
    set_session_manifest_text(ctx, mode="replace_all", new_text=VALID_MINIMAL_MANIFEST)

    result = set_session_manifest_text(
        ctx,
        mode="replace_lines",
        replace_lines=(1, 1000),
        new_text="replacement\n",
    )

    assert isinstance(result, SetManifestContentsResult)
    assert result.error is not None
    assert "exceeds file length" in result.error


def test_insert_lines_mode_success(ctx) -> None:
    """Test insert_lines mode with valid line number."""
    set_session_manifest_text(ctx, mode="replace_all", new_text=VALID_MINIMAL_MANIFEST)

    result = set_session_manifest_text(
        ctx,
        mode="insert_lines",
        insert_at_line_number=2,
        new_text="# Inserted comment\n",
    )

    assert isinstance(result, SetManifestContentsResult)
    assert result.error is None
    assert "Saved manifest" in result.message
    assert result.diff_summary is not None
    assert "+# Inserted comment" in result.diff_summary or "Inserted comment" in result.diff_summary

    content = get_session_manifest_content(ctx.session_id)
    assert "# Inserted comment" in content


def test_insert_lines_mode_missing_params(ctx) -> None:
    """Test insert_lines mode with missing parameters."""
    set_session_manifest_text(ctx, mode="replace_all", new_text=VALID_MINIMAL_MANIFEST)

    result = set_session_manifest_text(
        ctx,
        mode="insert_lines",
        new_text="inserted\n",
    )

    assert isinstance(result, SetManifestContentsResult)
    assert result.error is not None
    assert "requires insert_at_line_number" in result.error


def test_insert_lines_mode_out_of_range(ctx) -> None:
    """Test insert_lines mode with out-of-range line number."""
    set_session_manifest_text(ctx, mode="replace_all", new_text=VALID_MINIMAL_MANIFEST)

    result = set_session_manifest_text(
        ctx,
        mode="insert_lines",
        insert_at_line_number=1000,
        new_text="inserted\n",
    )

    assert isinstance(result, SetManifestContentsResult)
    assert result.error is not None
    assert "must be in range" in result.error


def test_replace_text_mode_single_occurrence(ctx) -> None:
    """Test replace_text mode with single occurrence."""
    set_session_manifest_text(ctx, mode="replace_all", new_text=VALID_MINIMAL_MANIFEST)

    result = set_session_manifest_text(
        ctx,
        mode="replace_text",
        replace_text="https://api.example.com",
        new_text="https://api.newdomain.com",
        replace_all_occurrences=False,
    )

    assert isinstance(result, SetManifestContentsResult)
    assert result.error is None
    assert "Saved manifest" in result.message
    assert "replaced 1 occurrence" in result.message
    assert result.diff_summary is not None

    content = get_session_manifest_content(ctx.session_id)
    assert "https://api.newdomain.com" in content
    assert "https://api.example.com" not in content


def test_replace_text_mode_multiple_occurrences_with_flag(ctx) -> None:
    """Test replace_text mode with multiple occurrences and replace_all_occurrences=True."""
    manifest_with_duplicates = VALID_MINIMAL_MANIFEST.replace("test", "users")
    set_session_manifest_text(ctx, mode="replace_all", new_text=manifest_with_duplicates)

    result = set_session_manifest_text(
        ctx,
        mode="replace_text",
        replace_text="users",
        new_text="customers",
        replace_all_occurrences=True,
    )

    assert isinstance(result, SetManifestContentsResult)
    assert result.error is None
    assert "replaced all" in result.message and "occurrences" in result.message

    content = get_session_manifest_content(ctx.session_id)
    assert "customers" in content
    assert "users" not in content


def test_replace_text_mode_multiple_occurrences_without_flag(ctx) -> None:
    """Test replace_text mode with multiple occurrences but replace_all_occurrences=False."""
    manifest_with_duplicates = VALID_MINIMAL_MANIFEST.replace("test", "users")
    set_session_manifest_text(ctx, mode="replace_all", new_text=manifest_with_duplicates)

    result = set_session_manifest_text(
        ctx,
        mode="replace_text",
        replace_text="users",
        new_text="customers",
        replace_all_occurrences=False,
    )

    assert isinstance(result, SetManifestContentsResult)
    assert result.error is not None
    assert "appears" in result.error and "times" in result.error
    assert "replace_all_occurrences=True" in result.error


def test_replace_text_mode_text_not_found(ctx) -> None:
    """Test replace_text mode when text is not found."""
    set_session_manifest_text(ctx, mode="replace_all", new_text=VALID_MINIMAL_MANIFEST)

    result = set_session_manifest_text(
        ctx,
        mode="replace_text",
        replace_text="text_that_does_not_exist_in_manifest",
        new_text="replacement",
    )

    assert isinstance(result, SetManifestContentsResult)
    assert result.error is not None
    assert "not found" in result.error


def test_replace_text_mode_missing_params(ctx) -> None:
    """Test replace_text mode with missing parameters."""
    set_session_manifest_text(ctx, mode="replace_all", new_text=VALID_MINIMAL_MANIFEST)

    result = set_session_manifest_text(
        ctx,
        mode="replace_text",
        new_text="replacement",
    )

    assert isinstance(result, SetManifestContentsResult)
    assert result.error is not None
    assert "requires replace_text parameter" in result.error


def test_invalid_mode(ctx) -> None:
    """Test with an invalid mode."""
    result = set_session_manifest_text(
        ctx,
        mode="invalid_mode",
        new_text="content",
    )

    assert isinstance(result, SetManifestContentsResult)
    assert result.error is not None
    assert "Unexpected mode" in result.error


def test_validation_warnings_included(ctx) -> None:
    """Test that validation warnings are included in the result."""
    invalid_manifest = """
version: "0.1.0"
type: DeclarativeSource
check:
  type: CheckStream
  stream_names: ["invalid"]
streams: []
"""

    result = set_session_manifest_text(
        ctx,
        mode="replace_all",
        new_text=invalid_manifest,
    )

    assert isinstance(result, SetManifestContentsResult)
    assert result.error is None
    assert isinstance(result.validation_warnings, list)
