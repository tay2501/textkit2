"""Regex / fixed-string search & replace."""

from __future__ import annotations

import re


def regex_replace(
    text: str,
    *,
    pattern: str = "",
    repl: str = "",
    ignore_case: bool = False,
    fixed: bool = False,
) -> str:
    r"""Replace every match of *pattern* in *text* with *repl*.

    Args:
        text: Input text.
        pattern: Regular expression to search.  An empty pattern is a no-op
            (identity transform) so the daemon hotkey path stays safe.
        repl: Replacement text; group references like ``\1`` are expanded
            unless *fixed* is set.
        ignore_case: Case-insensitive matching.
        fixed: Treat *pattern* and *repl* as literal strings — no regex
            metacharacters, no backslash expansion.

    Raises:
        ValueError: When *pattern* is not a valid regular expression.
    """
    if not pattern:
        return text
    flags = re.IGNORECASE if ignore_case else 0
    try:
        if fixed:
            # A callable replacement suppresses backslash expansion in repl.
            return re.sub(re.escape(pattern), lambda _m: repl, text, flags=flags)
        return re.sub(pattern, repl, text, flags=flags)
    except re.PatternError as exc:
        raise ValueError(f"invalid regex: {exc}") from exc
