"""Full-width / half-width character conversion (F-01, F-02)."""

import jaconv


def to_halfwidth(text: str) -> str:
    """Convert full-width ASCII/digits/katakana to half-width; hiragana is preserved."""
    return jaconv.z2h(text, ascii=True, digit=True, kana=True)


def to_fullwidth(text: str) -> str:
    """Convert half-width ASCII/digits/katakana to full-width."""
    return jaconv.h2z(text, ascii=True, digit=True, kana=True)


def to_enlarge_smallkana(text: str) -> str:
    """Expand small-form kana to normal size (ぁ→あ, ァ→ア, etc.)."""
    return jaconv.enlarge_smallkana(text)
