"""JSON formatting transforms (F-21, F-22).

Supported operations:
    F-21  json_format   — parse JSON and re-emit with indentation (pretty-print)
    F-22  json_compress — parse JSON and re-emit without whitespace (compact)
"""

from __future__ import annotations

import json
from typing import Any


def _load_json(text: str) -> Any:
    """Parse JSON text, raising ValueError on decode failure."""
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON: {exc}") from exc


def json_format(text: str, *, indent: int = 2) -> str:
    """Pretty-print JSON with the specified indentation (ensure_ascii=False)."""
    return json.dumps(_load_json(text), indent=indent, ensure_ascii=False)


def json_compress(text: str) -> str:
    """Compress JSON to a single compact line (ensure_ascii=False)."""
    return json.dumps(_load_json(text), separators=(",", ":"), ensure_ascii=False)
