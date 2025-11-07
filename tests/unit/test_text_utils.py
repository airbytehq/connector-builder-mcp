"""Unit tests for text manipulation utilities."""

import pytest

from connector_builder_mcp._text_utils import (
    insert_text_lines,
    replace_text_lines,
    unified_diff_with_context,
)


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
    result = replace_text_lines(lines, start_line, end_line, replacement_text)
    assert result == expected


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
    result = insert_text_lines(lines, insert_at_line, text_to_insert)
    assert result == expected


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
