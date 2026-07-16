"""Hiragana / katakana conversion."""

import jaconv


def to_katakana(text: str) -> str:
    """Convert hiragana to katakana (ひらがな → カタカナ)."""
    return jaconv.hira2kata(text)


def to_hiragana(text: str) -> str:
    """Convert katakana to hiragana (カタカナ → ひらがな)."""
    return jaconv.kata2hira(text)
