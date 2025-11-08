"""Unit tests for text manipulation utilities."""

import pytest

from connector_builder_mcp._text_utils import (
    insert_text_lines,
    replace_all_text,
    replace_text_content,
    replace_text_lines,
    unified_diff_with_context,
)


@pytest.mark.parametrize(
    "old_content,new_content,expected_diff_summary",
    [
        ("line1\nline2\nline3\n", "", "Deleted 3 lines"),
        # Replace with different line count
        ("line1\nline2\n", "new1\nnew2\nnew3\n", "Replaced 2 lines with 3 lines"),
        # Replace with same line count
        ("line1\nline2\n", "new1\nnew2\n", "Replaced 2 lines with 2 lines"),
        # Replace empty with content
        ("", "line1\nline2\n", "Replaced 0 lines with 2 lines"),
    ],
)
def test_replace_all_text(
    old_content: str,
    new_content: str,
    expected_diff_summary: str,
) -> None:
    """Test replace_all_text with various inputs."""
    result_content, diff_summary = replace_all_text(
        old_content=old_content,
        new_content=new_content,
    )
    assert result_content == new_content
    assert diff_summary == expected_diff_summary


@pytest.mark.parametrize(
    "existing_content,find_text,replacement_text,replace_all_occurrences,expected_content,expected_success_msg,expected_error",
    [
        (
            "line1\nold_value\nline3\n",
            "old_value",
            "new_value",
            False,
            "line1\nnew_value\nline3\n",
            "1 occurrence",
            None,
        ),
        # Multiple occurrences, replace_all_occurrences=True (success)
        (
            "old\nold\nold\n",
            "old",
            "new",
            True,
            "new\nnew\nnew\n",
            "all 3 occurrences",
            None,
        ),
        (
            "line1\nline2\n",
            "not_found",
            "replacement",
            False,
            "",
            "",
            "Text to replace not found: not_found",
        ),
        # Multiple occurrences, replace_all_occurrences=False (error)
        (
            "old\nold\nold\n",
            "old",
            "new",
            False,
            "",
            "",
            "Text appears 3 times. Use replace_all_occurrences=True",
        ),
        (
            "",
            "find",
            "replace",
            False,
            "",
            "",
            "Cannot replace text in empty or non-existent content",
        ),
    ],
)
def test_replace_text_content(
    existing_content: str,
    find_text: str,
    replacement_text: str,
    replace_all_occurrences: bool,
    expected_content: str,
    expected_success_msg: str,
    expected_error: str | None,
) -> None:
    """Test replace_text_content with various inputs."""
    new_content, success_msg, error = replace_text_content(
        existing_content=existing_content,
        find_text=find_text,
        replacement_text=replacement_text,
        replace_all_occurrences=replace_all_occurrences,
    )

    if expected_error:
        assert error is not None
        assert expected_error in error
    else:
        assert error is None
        assert new_content == expected_content
        assert expected_success_msg in success_msg


@pytest.mark.parametrize(
    "existing_content,start_line,end_line,expected_error",
    [
        # start_line > end_line
        ("line1\nline2\n", 2, 1, "1 <= start_line <= end_line"),
        # start_line < 1
        ("line1\nline2\n", 0, 1, "1 <= start_line <= end_line"),
        ("line1\nline2\n", 1, 10, "exceeds file length"),
    ],
)
def test_replace_text_lines_errors(
    existing_content: str,
    start_line: int,
    end_line: int,
    expected_error: str,
) -> None:
    """Test replace_text_lines error handling."""
    new_content, error = replace_text_lines(
        existing_content=existing_content,
        start_line=start_line,
        end_line=end_line,
        replacement_text="replacement\n",
    )
    assert error is not None
    assert expected_error in error


@pytest.mark.parametrize(
    "existing_content,insert_at_line,expected_error",
    [
        # insert_at_line < 1
        ("line1\nline2\n", 0, "must be in range 1..3"),
        # insert_at_line > num_lines + 1
        ("line1\nline2\n", 10, "must be in range 1..3"),
    ],
)
def test_insert_text_lines_errors(
    existing_content: str,
    insert_at_line: int,
    expected_error: str,
) -> None:
    """Test insert_text_lines error handling."""
    new_content, error = insert_text_lines(
        existing_content=existing_content,
        insert_at_line=insert_at_line,
        text_to_insert="inserted\n",
    )
    assert error is not None
    assert expected_error in error


@pytest.mark.parametrize(
    "lines,start_line,end_line,replacement_text,expected",
    [
        # Replace single line
        (
            ["line1\n", "line2\n", "line3\n"],
            2,
            2,
            "replaced\n",
            "line1\nreplaced\nline3\n",
        ),
        # Replace multiple lines
        (
            ["line1\n", "line2\n", "line3\n", "line4\n"],
            2,
            3,
            "replaced\n",
            "line1\nreplaced\nline4\n",
        ),
        # Replace with multiple lines
        (
            ["line1\n", "line2\n", "line3\n"],
            2,
            2,
            "new1\nnew2\n",
            "line1\nnew1\nnew2\nline3\n",
        ),
        # Replace at start
        (
            ["line1\n", "line2\n", "line3\n"],
            1,
            1,
            "replaced\n",
            "replaced\nline2\nline3\n",
        ),
        # Replace at end
        (
            ["line1\n", "line2\n", "line3\n"],
            3,
            3,
            "replaced\n",
            "line1\nline2\nreplaced\n",
        ),
    ],
)
def test_replace_text_lines(
    lines: list[str],
    start_line: int,
    end_line: int,
    replacement_text: str,
    expected: str,
) -> None:
    """Test replace_text_lines with various inputs."""
    existing_content = "".join(lines)
    new_content, error = replace_text_lines(
        existing_content=existing_content,
        start_line=start_line,
        end_line=end_line,
        replacement_text=replacement_text,
    )
    assert error is None, f"Unexpected error: {error}"
    assert new_content == expected


@pytest.mark.parametrize(
    "lines,insert_at_line,text_to_insert,expected",
    [
        # Insert at beginning
        (
            ["line1\n", "line2\n", "line3\n"],
            1,
            "inserted\n",
            "inserted\nline1\nline2\nline3\n",
        ),
        # Insert in middle
        (
            ["line1\n", "line2\n", "line3\n"],
            2,
            "inserted\n",
            "line1\ninserted\nline2\nline3\n",
        ),
        # Insert at end
        (
            ["line1\n", "line2\n", "line3\n"],
            4,
            "inserted\n",
            "line1\nline2\nline3\ninserted\n",
        ),
        # Insert multiple lines
        (
            ["line1\n", "line2\n"],
            2,
            "new1\nnew2\n",
            "line1\nnew1\nnew2\nline2\n",
        ),
        # Insert into empty
        (
            [],
            1,
            "inserted\n",
            "inserted\n",
        ),
    ],
)
def test_insert_text_lines(
    lines: list[str],
    insert_at_line: int,
    text_to_insert: str,
    expected: str,
) -> None:
    """Test insert_text_lines with various inputs."""
    existing_content = "".join(lines)
    new_content, error = insert_text_lines(
        existing_content=existing_content,
        insert_at_line=insert_at_line,
        text_to_insert=text_to_insert,
    )
    assert error is None, f"Unexpected error: {error}"
    assert new_content == expected


@pytest.mark.parametrize(
    "old_text,new_text,expected_contains",
    [
        # No changes
        (
            "line1\nline2\nline3\n",
            "line1\nline2\nline3\n",
            "[no changes]",
        ),
        # Single line changed
        (
            "line1\nline2\nline3\n",
            "line1\nmodified\nline3\n",
            "-line2",
        ),
        # Line added
        (
            "line1\nline2\n",
            "line1\nline2\nline3\n",
            "+line3",
        ),
        # Line removed
        (
            "line1\nline2\nline3\n",
            "line1\nline3\n",
            "-line2",
        ),
        # Multiple changes
        (
            "line1\nline2\nline3\nline4\n",
            "line1\nmodified2\nmodified3\nline4\n",
            "-line2",
        ),
    ],
)
def test_unified_diff_with_context(
    old_text: str,
    new_text: str,
    expected_contains: str,
) -> None:
    """Test unified_diff_with_context with various inputs."""
    result = unified_diff_with_context(old_text, new_text, context=2)
    assert expected_contains in result

    # Verify diff headers are present (unless no changes)
    if expected_contains != "[no changes]":
        assert "--- before" in result
        assert "+++ after" in result
