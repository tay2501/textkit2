"""Line-oriented transforms: trim, dedupe, sort.

All functions are pure: fn(text: str, **kwargs) -> str.
Line endings are normalised to LF on entry; trailing newline is preserved.
"""

from __future__ import annotations

import locale
import unicodedata


def _normalise(text: str) -> tuple[list[str], bool]:
    s = text.replace("\r\n", "\n").replace("\r", "\n")
    trailing = s.endswith("\n")
    lines = s.split("\n")
    # Remove the empty sentinel that split() appends when text ends with "\n"
    if trailing:
        lines = lines[:-1]
    return lines, trailing


def _join(lines: list[str], trailing: bool) -> str:
    result = "\n".join(lines)
    return result + "\n" if trailing else result


def trim_lines(text: str, *, both: bool = False) -> str:
    """Strip trailing (or both-sided) whitespace from each line."""
    lines, trailing = _normalise(text)
    fn = str.strip if both else str.rstrip
    return _join([fn(line) for line in lines], trailing)


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


def sort_lines(
    text: str,
    *,
    reverse: bool = False,
    numeric: bool = False,
    ignore_case: bool = False,
) -> str:
    """Sort lines using locale-aware collation (strxfrm); main() must call setlocale first."""
    lines, trailing = _normalise(text)

    if numeric:

        def _num_key(line: str) -> tuple[int, float, str]:
            try:
                return (0, float(line.strip()), line)
            except ValueError:
                return (1, 0.0, line)

        sorted_lines = sorted(lines, key=_num_key, reverse=reverse)
    else:

        def _strxfrm_key(line: str) -> str:
            k = line.casefold() if ignore_case else line
            return locale.strxfrm(k)

        sorted_lines = sorted(lines, key=_strxfrm_key, reverse=reverse)

    return _join(sorted_lines, trailing)
