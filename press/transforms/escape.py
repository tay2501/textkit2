"""Unicode escape and HTML entity conversion (F-11, F-12)."""

import html


def encode_unicode_escape(text: str) -> str:
    r"""Encode non-ASCII characters to \uXXXX sequences (ASCII chars preserved)."""
    return text.encode("unicode_escape").decode("ascii")


def decode_unicode_escape(text: str) -> str:
    r"""Decode \uXXXX escape sequences to readable Unicode characters."""
    try:
        return text.encode("raw_unicode_escape").decode("unicode_escape")
    except (UnicodeDecodeError, ValueError) as exc:
        raise ValueError(f"Failed to decode Unicode escapes: {exc}") from exc


def decode_html_entities(text: str) -> str:
    """Decode HTML entities (&amp;, &lt;, &#x3042;, etc.) to Unicode characters."""
    return html.unescape(text)
