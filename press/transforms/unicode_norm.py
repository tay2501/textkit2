"""Unicode normalization transforms: NFC, NFD, NFKC, NFKD."""

from __future__ import annotations

import unicodedata

__all__ = ["check_norm", "to_nfc", "to_nfd", "to_nfkc", "to_nfkd"]


def check_norm(text: str) -> str:
    """Report which Unicode normalization forms the text already satisfies.

    Checks all four forms (NFC, NFD, NFKC, NFKD) using
    ``unicodedata.is_normalized()`` and returns a human-readable table.

    Args:
        text: Input text to inspect.

    Returns:
        A four-line string with columns aligned at position 6, each line
        formatted as ``"<FORM>  yes"`` or ``"<FORM>  no"``.
    """
    n = unicodedata.is_normalized
    nfc = "yes" if n("NFC", text) else "no"
    nfd = "yes" if n("NFD", text) else "no"
    nfkc = "yes" if n("NFKC", text) else "no"
    nfkd = "yes" if n("NFKD", text) else "no"
    return f"NFC   {nfc}\nNFD   {nfd}\nNFKC  {nfkc}\nNFKD  {nfkd}\n"


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
