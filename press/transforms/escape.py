"""Unicode escape and HTML entity conversion (F-11, F-12)."""

import html


def encode_unicode_escape(text: str) -> str:
    r"""Encode non-ASCII characters to \\uXXXX escape sequences.

    ASCII characters (U+0000–U+007F) are preserved as-is.

    Args:
        text: Input text to encode.

    Returns:
        Text with non-ASCII characters replaced by \\uXXXX sequences.
    """
    return text.encode("unicode_escape").decode("ascii")


def decode_unicode_escape(text: str) -> str:
    r"""Decode \\uXXXX escape sequences to readable Unicode characters.

    Args:
        text: Text containing \\uXXXX escape sequences.

    Returns:
        Text with escape sequences replaced by the corresponding characters.

    Raises:
        ValueError: If the input contains malformed escape sequences.
        UnicodeDecodeError: If decoding fails.
    """
    try:
        return text.encode("raw_unicode_escape").decode("unicode_escape")
    except (UnicodeDecodeError, ValueError) as exc:
        raise ValueError(f"Failed to decode Unicode escapes: {exc}") from exc


def decode_html_entities(text: str) -> str:
    """Decode HTML entities to their Unicode character equivalents.

    Handles named entities (&lt;, &amp;, etc.) and numeric references
    (&#x3042; or &#12354;).

    Args:
        text: HTML-encoded text.

    Returns:
        Text with HTML entities replaced by the corresponding characters.
    """
    return html.unescape(text)
