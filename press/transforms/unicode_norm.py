"""Unicode normalization transforms: NFC, NFD, NFKC, NFKD."""

from __future__ import annotations

import unicodedata

__all__ = ["to_nfc", "to_nfd", "to_nfkc", "to_nfkd"]


def to_nfc(text: str) -> str:
    """Normalize text to NFC (canonical composition).

    Combines decomposed characters (e.g. macOS NFD filenames) into
    precomposed form used by Windows and most web standards.

    Args:
        text: Input text to transform.

    Returns:
        NFC-normalized text.
    """
    return text if unicodedata.is_normalized("NFC", text) else unicodedata.normalize("NFC", text)


def to_nfd(text: str) -> str:
    """Normalize text to NFD (canonical decomposition).

    Decomposes precomposed characters into base character plus combining
    marks (e.g. the form used by macOS HFS+ for filenames).

    Args:
        text: Input text to transform.

    Returns:
        NFD-normalized text.
    """
    return text if unicodedata.is_normalized("NFD", text) else unicodedata.normalize("NFD", text)


def to_nfkc(text: str) -> str:
    """Normalize text to NFKC (compatibility composition).

    Folds compatibility characters (full-width Latin, ligatures, etc.)
    into their canonical equivalents and then applies canonical composition.

    Args:
        text: Input text to transform.

    Returns:
        NFKC-normalized text.
    """
    return text if unicodedata.is_normalized("NFKC", text) else unicodedata.normalize("NFKC", text)


def to_nfkd(text: str) -> str:
    """Normalize text to NFKD (compatibility decomposition).

    Folds compatibility characters and then applies canonical decomposition.

    Args:
        text: Input text to transform.

    Returns:
        NFKD-normalized text.
    """
    return text if unicodedata.is_normalized("NFKD", text) else unicodedata.normalize("NFKD", text)
