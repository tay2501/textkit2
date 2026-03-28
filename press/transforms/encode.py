"""Encode / decode transforms (F-17 to F-20).

Supported conversions:
    F-17  base64_encode — UTF-8 text → Base64 string
    F-18  base64_decode — Base64 string → UTF-8 text
    F-19  url_encode    — percent-encode a URL string
    F-20  url_decode    — decode a percent-encoded URL string
"""

from __future__ import annotations

import base64
import urllib.parse


def base64_encode(text: str) -> str:
    """Encode text to a Base64 string.

    The text is first encoded as UTF-8 bytes, then converted to a Base64
    string.  The result contains no trailing newline.

    Args:
        text: Input text to encode.

    Returns:
        Base64-encoded string without a trailing newline.
    """
    encoded_bytes = base64.b64encode(text.encode("utf-8"))
    return encoded_bytes.decode("ascii")


def base64_decode(text: str) -> str:
    """Decode a Base64 string back to text.

    Args:
        text: Base64-encoded string.

    Returns:
        Decoded UTF-8 text.

    Raises:
        ValueError: If the input is not valid Base64 or the decoded bytes
            cannot be interpreted as UTF-8.
    """
    try:
        decoded_bytes = base64.b64decode(text, validate=True)
    except Exception as exc:
        raise ValueError(f"Invalid Base64 input: {exc}") from exc
    try:
        return decoded_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(f"Decoded bytes are not valid UTF-8: {exc}") from exc


def url_encode(text: str) -> str:
    """Percent-encode all characters in text using UTF-8.

    All characters including ``/`` and ``@`` are encoded (``safe=''``).

    Args:
        text: Input text to encode.

    Returns:
        Percent-encoded string.
    """
    return urllib.parse.quote(text, safe="")


def url_decode(text: str) -> str:
    """Decode a percent-encoded URL string.

    ``+`` is NOT treated as a space; use ``urllib.parse.unquote_plus`` if
    that behaviour is desired.

    Args:
        text: Percent-encoded string.

    Returns:
        Decoded string.
    """
    return urllib.parse.unquote(text)
