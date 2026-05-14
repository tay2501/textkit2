"""Encode / decode transforms (F-17 to F-20).

Supported conversions:
    F-17  base64_encode — UTF-8 text → Base64 string
    F-18  base64_decode — Base64 string → UTF-8 text
    F-19  url_encode    — percent-encode a URL string
    F-20  url_decode    — decode a percent-encoded URL string
"""

from __future__ import annotations

import base64
import binascii
import urllib.parse


def base64_encode(text: str) -> str:
    """Encode text to Base64 (UTF-8 bytes → ASCII Base64 string, no trailing newline)."""
    encoded_bytes = base64.b64encode(text.encode("utf-8"))
    return encoded_bytes.decode("ascii")


def base64_decode(text: str) -> str:
    """Decode Base64 string to UTF-8 text."""
    try:
        decoded_bytes = base64.b64decode(text, validate=True)
    except binascii.Error as exc:
        raise ValueError(f"Invalid Base64 input: {exc}") from exc
    try:
        return decoded_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(f"Decoded bytes are not valid UTF-8: {exc}") from exc


def url_encode(text: str) -> str:
    """Percent-encode text using UTF-8 (safe='', all chars including / and @ are encoded)."""
    return urllib.parse.quote(text, safe="")


def url_decode(text: str) -> str:
    """Decode a percent-encoded URL string (+ is NOT treated as space)."""
    return urllib.parse.unquote(text)
