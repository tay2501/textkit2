"""Regex / fixed-string search & replace."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence


def regex_replace(
    text: str,
    *,
    patterns: Sequence[str] | None = None,
    repl: str = "",
    ignore_case: bool = False,
    fixed: bool = False,
) -> str:
    r"""Replace every match of any of *patterns* in *text* with *repl*.

    Several patterns behave like repeated ``grep -e`` / ``rg -e``: a match of
    any of them is replaced.  Group numbers count across the patterns in the
    order given.

    Args:
        text: Input text.
        patterns: Regular expressions to search.  At least one is required —
            the CLI enforces ``-e`` and every other path (hotkey, ``chain``
            step) fails here, so no path silently returns the text unchanged.
        repl: Replacement text; group references like ``\1`` are expanded
            unless *fixed* is set.
        ignore_case: Case-insensitive matching.
        fixed: Treat *patterns* and *repl* as literal strings — no regex
            metacharacters, no backslash expansion.

    Raises:
        ValueError: When no pattern is given or a pattern is not a valid
            regular expression.
    """
    if not patterns:
        raise ValueError("no pattern: pass -e/--regexp")
    parts = [re.escape(p) for p in patterns] if fixed else list(patterns)
    combined = parts[0] if len(parts) == 1 else "|".join(f"(?:{p})" for p in parts)
    flags = re.IGNORECASE if ignore_case else 0
    try:
        if fixed:
            # A callable replacement suppresses backslash expansion in repl.
            return re.sub(combined, lambda _m: repl, text, flags=flags)
        return re.sub(combined, repl, text, flags=flags)
    except re.PatternError as exc:
        raise ValueError(f"invalid regex: {exc}") from exc
