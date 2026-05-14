"""Whitespace and line normalization (F-03)."""

import re

_WHITESPACE_RE = re.compile(r"[ \t]+")


def _clean_line(line: str) -> str:
    line = line.replace("\u3000", " ")
    line = _WHITESPACE_RE.sub(" ", line)
    return line.strip()


def normalize_whitespace(text: str) -> str:
    """Normalize whitespace: collapse runs, strip leading/trailing, remove blank lines."""
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    return "\n".join(cleaned for line in normalized.split("\n") if (cleaned := _clean_line(line)))
