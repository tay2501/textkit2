"""Underscore / hyphen separator conversion (F-07)."""


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
