"""Line-oriented transforms: trim, dedupe, sort, number, reverse.

All functions are pure: fn(text: str, **kwargs) -> str.
Line endings are normalised to LF on entry; trailing newline is preserved.
"""

from __future__ import annotations

import locale
import re
import unicodedata

from press.transforms.lineending import to_lf

# GNU sort -n's number: leading blanks, optional minus, digits with at most one
# decimal point.  "1e3" reads as 1 and "inf" as no number (that is sort -g).
_LEADING_NUMBER_RE = re.compile(r"[ \t]*(-?(?:\d+\.?\d*|\.\d+))")


def _normalise(text: str) -> tuple[list[str], bool]:
    s = to_lf(text)
    trailing = s.endswith("\n")
    lines = s.split("\n")
    # Remove the empty sentinel that split() appends when text ends with "\n"
    if trailing:
        lines = lines[:-1]
    return lines, trailing


def _join(lines: list[str], trailing: bool) -> str:
    result = "\n".join(lines)
    return result + "\n" if trailing else result


def trim_lines(text: str, *, trailing: bool = False) -> str:
    """Strip whitespace from both ends of each line (only the end with *trailing*)."""
    lines, ends_with_newline = _normalise(text)
    fn = str.rstrip if trailing else str.strip
    return _join([fn(line) for line in lines], ends_with_newline)


def dedupe_lines(text: str, *, ignore_case: bool = False, adjacent: bool = False) -> str:
    """Remove duplicate lines (first-occurrence order); NFC-normalizes comparison keys."""
    lines, trailing = _normalise(text)

    def _key(line: str) -> str:
        k = unicodedata.normalize("NFC", line)
        return k.casefold() if ignore_case else k

    if adjacent:
        result: list[str] = []
        prev: str | None = None
        for line in lines:
            k = _key(line)
            if k != prev:
                result.append(line)
                prev = k
    else:
        seen: dict[str, str] = {}
        for line in lines:
            k = _key(line)
            if k not in seen:
                seen[k] = line
        result = list(seen.values())

    return _join(result, trailing)


def number_lines(text: str, *, starting_line_number: int = 1, number_separator: str = "\t") -> str:
    """Prefix each line with its line number, joined by *number_separator*."""
    lines, trailing = _normalise(text)
    numbered = [
        f"{i}{number_separator}{line}" for i, line in enumerate(lines, starting_line_number)
    ]
    return _join(numbered, trailing)


def reverse_lines(text: str) -> str:
    """Reverse the order of lines."""
    lines, trailing = _normalise(text)
    return _join(lines[::-1], trailing)


def sort_lines(
    text: str,
    *,
    reverse: bool = False,
    numeric: bool = False,
    ignore_case: bool = False,
) -> str:
    """Sort lines using locale-aware collation (strxfrm); main() must call setlocale first.

    *numeric* follows GNU ``sort -n``: lines compare by their leading number
    (optional blanks and ``-``, digits, one decimal point — no exponent, no
    ``inf``), a line without one counts as 0, and ties fall back to comparing
    the whole line.
    """
    lines, trailing = _normalise(text)

    def _strxfrm_key(line: str) -> str:
        k = line.casefold() if ignore_case else line
        return locale.strxfrm(k)

    if numeric:

        def _num_key(line: str) -> tuple[float, str]:
            match = _LEADING_NUMBER_RE.match(line)
            number = float(match.group(1)) if match else 0.0
            return (number, _strxfrm_key(line))

        sorted_lines = sorted(lines, key=_num_key, reverse=reverse)
    else:
        sorted_lines = sorted(lines, key=_strxfrm_key, reverse=reverse)

    return _join(sorted_lines, trailing)
