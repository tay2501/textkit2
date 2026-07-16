"""Text statistics report (count command)."""

from __future__ import annotations


def count_text(text: str) -> str:
    """Report character, word, line, and UTF-8 byte counts for *text*.

    ``chars`` counts every character including whitespace; ``non-space``
    excludes all whitespace (useful for Japanese manuscript counting, where
    words are not space-delimited).  ``words`` splits on whitespace runs,
    matching ``wc -w`` semantics.
    """
    non_space = sum(1 for ch in text if not ch.isspace())
    rows = (
        ("chars", len(text)),
        ("non-space", non_space),
        ("words", len(text.split())),
        ("lines", len(text.splitlines())),
        ("bytes-utf8", len(text.encode("utf-8"))),
    )
    return "".join(f"{label:<11}{value}\n" for label, value in rows)
