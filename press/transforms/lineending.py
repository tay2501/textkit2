"""Line-ending conversion: CRLF / LF / CR (F-04, F-05, F-06)."""

import re

# Matches any line ending: CRLF, CR, or LF (in that order to avoid double conversion)
_ANY_NEWLINE = re.compile(r"\r\n|\r|\n")


def _normalize_to_lf(text: str) -> str:
    """Internal helper: convert all line endings to LF."""
    return _ANY_NEWLINE.sub("\n", text)


def to_crlf(text: str) -> str:
    r"""Convert all line endings to CRLF (\r\n)."""
    return _normalize_to_lf(text).replace("\n", "\r\n")


def to_lf(text: str) -> str:
    r"""Convert all line endings to LF (\n)."""
    return _normalize_to_lf(text)


def to_cr(text: str) -> str:
    r"""Convert all line endings to CR (\r)."""
    return _normalize_to_lf(text).replace("\n", "\r")
