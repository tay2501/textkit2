"""Underscore / hyphen separator conversion, comma stripping, and digits-only (F-07)."""

import re

_FULLWIDTH_COMMA = "，"  # noqa: RUF001 — intentional U+FF0C
_NON_DIGIT_RE = re.compile(r"[^0-9０-９]")  # noqa: RUF001 - intentional U+FF10-U+FF19


def digits_only(text: str) -> str:
    """Remove all characters except ASCII and full-width digits.

    Keeps half-width 0-9 and full-width ０-９ (U+FF10–U+FF19).
    All other characters — currency symbols, commas, periods, spaces — are removed.
    Useful when amounts may use either comma or period as the thousands separator
    (e.g. ¥1,234 or €1.234 → 1234).

    Args:
        text: Input text containing a number with surrounding noise.

    Returns:
        Text with only digit characters remaining.
    """
    return _NON_DIGIT_RE.sub("", text)


def strip_commas(text: str) -> str:
    """Remove comma characters from text.

    Removes both ASCII comma , (U+002C) and full-width comma (U+FF0C).
    Useful for cleaning numbers copied from the web before pasting into Excel.

    Args:
        text: Input text containing commas.

    Returns:
        Text with all comma characters removed.
    """
    return text.replace(",", "").replace(_FULLWIDTH_COMMA, "")


def underscore_to_hyphen(text: str) -> str:
    """Replace all underscores with hyphens.

    Case is preserved. Only ASCII underscore (U+005F) is replaced.

    Args:
        text: Input text with underscore separators.

    Returns:
        Text with underscores replaced by hyphens.
    """
    return text.replace("_", "-")


def hyphen_to_underscore(text: str) -> str:
    """Replace all hyphens with underscores.

    Case is preserved. Only ASCII hyphen-minus (U+002D) is replaced.

    Args:
        text: Input text with hyphen separators.

    Returns:
        Text with hyphens replaced by underscores.
    """
    return text.replace("-", "_")
