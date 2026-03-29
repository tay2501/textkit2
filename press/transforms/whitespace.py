"""Whitespace and line normalization (F-03)."""

import re

_WHITESPACE_RE = re.compile(r"[ \t]+")


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

    def _clean(line: str) -> str:
        line = line.replace("\u3000", " ")
        line = _WHITESPACE_RE.sub(" ", line)
        return line.strip()

    return "\n".join(cleaned for line in normalized.split("\n") if (cleaned := _clean(line)))
