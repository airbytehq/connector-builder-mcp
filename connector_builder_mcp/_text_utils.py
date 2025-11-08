"""Generic text manipulation utilities."""

import difflib


def replace_all_text(
    *,
    old_content: str,
    new_content: str,
) -> tuple[str, str]:
    """Replace entire content with new content.

    Args:
        old_content: Original text content
        new_content: New text content to replace with

    Returns:
        Tuple of (new_content, diff_summary)
    """
    old_line_count = len(old_content.splitlines())
    new_line_count = len(new_content.splitlines())

    if new_content == "":
        diff_summary = f"Deleted {old_line_count} lines"
    else:
        diff_summary = f"Replaced {old_line_count} lines with {new_line_count} lines"

    return new_content, diff_summary


def replace_text_lines(
    *,
    existing_content: str,
    start_line: int,
    end_line: int,
    replacement_text: str,
) -> tuple[str, str | None]:
    """Replace a range of lines in text with new content.

    Args:
        existing_content: Original text content
        start_line: Starting line number (1-indexed, inclusive)
        end_line: Ending line number (1-indexed, inclusive)
        replacement_text: Text to replace the lines with

    Returns:
        Tuple of (new_content, error_message)
        If error_message is not None, new_content should be ignored

    Raises:
        No exceptions - returns error messages via tuple
    """
    lines = existing_content.splitlines(keepends=True)
    num_lines = len(lines)

    # Guard: validate line range
    if not (1 <= start_line <= end_line):
        return (
            "",
            f"replace_lines requires 1 <= start_line <= end_line, got start={start_line}, end={end_line}",
        )

    if end_line > num_lines:
        return (
            "",
            f"replace_lines end_line={end_line} exceeds file length ({num_lines} lines)",
        )

    # Perform replacement
    start_idx = start_line - 1
    end_idx = end_line  # end_line is inclusive, so end_idx is exclusive

    replacement_lines = replacement_text.splitlines(keepends=True)
    new_lines = lines[:start_idx] + replacement_lines + lines[end_idx:]

    return "".join(new_lines), None


def insert_text_lines(
    *,
    existing_content: str,
    insert_at_line: int,
    text_to_insert: str,
) -> tuple[str, str | None]:
    """Insert text before a specific line number.

    Args:
        existing_content: Original text content
        insert_at_line: Line number to insert before (1-indexed)
        text_to_insert: Text to insert

    Returns:
        Tuple of (new_content, error_message)
        If error_message is not None, new_content should be ignored

    Raises:
        No exceptions - returns error messages via tuple
    """
    lines = existing_content.splitlines(keepends=True)
    num_lines = len(lines)

    # Guard: validate insert position
    if not (1 <= insert_at_line <= num_lines + 1):
        return (
            "",
            f"insert_at_line_number must be in range 1..{num_lines + 1}, got {insert_at_line}",
        )

    # Perform insertion
    insert_idx = insert_at_line - 1
    insert_lines = text_to_insert.splitlines(keepends=True)
    new_lines = lines[:insert_idx] + insert_lines + lines[insert_idx:]

    return "".join(new_lines), None


def replace_text_content(
    *,
    existing_content: str,
    find_text: str,
    replacement_text: str,
    replace_all_occurrences: bool = False,
) -> tuple[str, str, str | None]:
    """Find and replace text content.

    Args:
        existing_content: Original text content
        find_text: Text to find and replace
        replacement_text: Text to replace with
        replace_all_occurrences: If True, replace all occurrences; if False, fail if multiple matches

    Returns:
        Tuple of (new_content, success_message, error_message)
        If error_message is not None, new_content and success_message should be ignored

    Raises:
        No exceptions - returns error messages via tuple
    """
    # Guard: empty content check
    if not existing_content:
        return "", "", "Cannot replace text in empty or non-existent content"

    # Guard: find text and count occurrences
    occurrence_count = existing_content.count(find_text)

    if occurrence_count == 0:
        truncated = find_text[:100] + ("..." if len(find_text) > 100 else "")
        return "", "", f"Text to replace not found: {truncated}"

    if occurrence_count > 1 and not replace_all_occurrences:
        return (
            "",
            "",
            f"Text appears {occurrence_count} times. Use replace_all_occurrences=True to replace all, or provide more context to make the match unique.",
        )

    # Perform replacement
    if replace_all_occurrences:
        new_content = existing_content.replace(find_text, replacement_text)
        success_msg = f"all {occurrence_count} occurrences"
    else:
        new_content = existing_content.replace(find_text, replacement_text, 1)
        success_msg = "1 occurrence"

    return new_content, success_msg, None


def unified_diff_with_context(old_text: str, new_text: str, context: int = 2) -> str:
    """Generate a unified diff between two text strings with context lines.

    Args:
        old_text: Original text content
        new_text: Modified text content
        context: Number of context lines to show around changes (default: 2)

    Returns:
        Unified diff string, or "[no changes]" if texts are identical
    """
    old_lines = old_text.splitlines(keepends=True)
    new_lines = new_text.splitlines(keepends=True)

    diff_lines = difflib.unified_diff(
        old_lines,
        new_lines,
        fromfile="before",
        tofile="after",
        n=context,
        lineterm="",
    )

    diff = "\n".join(diff_lines)
    return diff or "[no changes]"
