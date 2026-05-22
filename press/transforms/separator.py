"""Underscore / hyphen separator conversion, and comma stripping (F-07)."""

_FULLWIDTH_COMMA = "，"  # noqa: RUF001 — intentional U+FF0C


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
