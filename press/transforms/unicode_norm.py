"""Unicode normalization transforms: NFC, NFD, NFKC, NFKD."""

from __future__ import annotations

import unicodedata
from typing import Literal

__all__ = ["check_norm", "to_nfc", "to_nfd", "to_nfkc", "to_nfkd"]


def check_norm(text: str) -> str:
    """Report which Unicode normalization forms the text already satisfies."""
    n = unicodedata.is_normalized
    forms: tuple[Literal["NFC", "NFD", "NFKC", "NFKD"], ...] = ("NFC", "NFD", "NFKC", "NFKD")
    return "".join(f"{form:<6}{'yes' if n(form, text) else 'no'}\n" for form in forms)


def to_nfc(text: str) -> str:
    """Normalize to NFC (canonical composition — Mac→Windows fix)."""
    return text if unicodedata.is_normalized("NFC", text) else unicodedata.normalize("NFC", text)


def to_nfd(text: str) -> str:
    """Normalize to NFD (canonical decomposition)."""
    return text if unicodedata.is_normalized("NFD", text) else unicodedata.normalize("NFD", text)


def to_nfkc(text: str) -> str:
    """Normalize to NFKC (compatibility composition — folds full-width, ligatures, etc.)."""
    return text if unicodedata.is_normalized("NFKC", text) else unicodedata.normalize("NFKC", text)


def to_nfkd(text: str) -> str:
    """Normalize to NFKD (compatibility decomposition)."""
    return text if unicodedata.is_normalized("NFKD", text) else unicodedata.normalize("NFKD", text)
