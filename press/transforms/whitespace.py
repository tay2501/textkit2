"""Whitespace and line normalization (F-03)."""

import re


def normalize_whitespace(text: str) -> str:
    """Normalize whitespace in text.

    Per-line processing:
    - Strip leading/trailing whitespace (including full-width spaces U+3000)
    - Collapse multiple consecutive whitespace characters into a single space
    - Remove blank lines after stripping

    Args:
        text: Input text with irregular whitespace.

    Returns:
        Text with normalized whitespace. Empty string if input is blank.
    """
    # Normalize line endings to LF first for consistent processing
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")

    lines = normalized.split("\n")
    cleaned: list[str] = []
    for line in lines:
        # Replace full-width space (U+3000) with regular space
        line = line.replace("\u3000", " ")
        # Collapse any whitespace run (tabs, multiple spaces) to single space
        line = re.sub(r"[ \t]+", " ", line)
        # Strip leading/trailing spaces
        line = line.strip()
        if line:
            cleaned.append(line)

    return "\n".join(cleaned)
