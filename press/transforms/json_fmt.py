"""JSON formatting transforms (F-21, F-22).

Supported operations:
    F-21  json_format   — parse JSON and re-emit with indentation (pretty-print)
    F-22  json_compress — parse JSON and re-emit without whitespace (compact)
"""

from __future__ import annotations

import json


def json_format(text: str, *, indent: int = 2) -> str:
    """Pretty-print JSON text with the specified indentation.

    Japanese and other non-ASCII characters are output as-is
    (``ensure_ascii=False``).

    Args:
        text:   Input JSON text.
        indent: Number of spaces per indentation level (default: 2).

    Returns:
        Formatted (pretty-printed) JSON string.

    Raises:
        ValueError: If ``text`` is not valid JSON, with a message prefixed
            by ``"Invalid JSON: "``.
    """
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON: {exc}") from exc
    return json.dumps(data, indent=indent, ensure_ascii=False)


def json_compress(text: str) -> str:
    """Compress JSON text to a single-line compact representation.

    All unnecessary whitespace is removed.  Japanese and other non-ASCII
    characters are output as-is (``ensure_ascii=False``).

    Args:
        text: Input JSON text.

    Returns:
        Compact JSON string with no extra whitespace.

    Raises:
        ValueError: If ``text`` is not valid JSON, with a message prefixed
            by ``"Invalid JSON: "``.
    """
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON: {exc}") from exc
    return json.dumps(data, separators=(",", ":"), ensure_ascii=False)
