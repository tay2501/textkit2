"""Underscore / hyphen separator conversion, comma stripping, and digits-only (F-07)."""

import re

_FULLWIDTH_COMMA = "，"  # noqa: RUF001 — intentional U+FF0C
_NON_DIGIT_RE = re.compile(r"[^0-9０-９]")  # noqa: RUF001 - intentional U+FF10-U+FF19


def digits_only(text: str) -> str:
    """Remove all characters except ASCII and full-width digits (e.g. ¥1,234 → 1234)."""
    return _NON_DIGIT_RE.sub("", text)


def strip_commas(text: str) -> str:
    """Remove ASCII and full-width commas (e.g. 1,234 → 1234)."""
    return text.replace(",", "").replace(_FULLWIDTH_COMMA, "")


def underscore_to_hyphen(text: str) -> str:
    """Replace all ASCII underscores with hyphens."""
    return text.replace("_", "-")


def hyphen_to_underscore(text: str) -> str:
    """Replace all ASCII hyphens with underscores."""
    return text.replace("-", "_")
