"""Generic text manipulation utilities."""


def replace_text_lines(
    lines: list[str],
    start_line: int,
    end_line: int,
    replacement_text: str,
) -> str:
    """Replace a range of lines in text with new content.

    Args:
        lines: List of lines (with line endings preserved)
        start_line: Starting line number (1-indexed, inclusive)
        end_line: Ending line number (1-indexed, inclusive)
        replacement_text: Text to replace the lines with

    Returns:
        Modified text as a single string
    """
    start_idx = start_line - 1
    end_idx = end_line  # end_line is inclusive, so end_idx is exclusive

    replacement_lines = replacement_text.splitlines(keepends=True)

    new_lines = lines[:start_idx] + replacement_lines + lines[end_idx:]
    return "".join(new_lines)


def insert_text_lines(
    lines: list[str],
    insert_at_line: int,
    text_to_insert: str,
) -> str:
    """Insert text before a specific line number.

    Args:
        lines: List of lines (with line endings preserved)
        insert_at_line: Line number to insert before (1-indexed)
        text_to_insert: Text to insert

    Returns:
        Modified text as a single string
    """
    insert_idx = insert_at_line - 1

    insert_lines = text_to_insert.splitlines(keepends=True)

    new_lines = lines[:insert_idx] + insert_lines + lines[insert_idx:]
    return "".join(new_lines)
