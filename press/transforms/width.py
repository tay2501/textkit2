"""Full-width / half-width character conversion (F-01, F-02)."""

import jaconv


def to_halfwidth(text: str) -> str:
    """Convert full-width ASCII, digits, spaces, and katakana to half-width.

    Hiragana is preserved unchanged.

    Args:
        text: Input text containing full-width characters.

    Returns:
        Text with full-width characters converted to half-width equivalents.
    """
    # ascii=True: full-width ASCII → half-width
    # digit=True: full-width digits → half-width
    # kana=True:  full-width katakana → half-width katakana
    return jaconv.z2h(text, ascii=True, digit=True, kana=True)


def to_fullwidth(text: str) -> str:
    """Convert half-width ASCII, digits, spaces, and katakana to full-width.

    Args:
        text: Input text containing half-width characters.

    Returns:
        Text with half-width characters converted to full-width equivalents.
    """
    return jaconv.h2z(text, ascii=True, digit=True, kana=True)


def to_enlarge_smallkana(text: str) -> str:
    """Convert small-form kana to normal-size kana (hiragana and katakana).

    Applies to both hiragana (ぁぃぅぇぉっゃゅょ → あいうえおつやゆよ) and
    katakana (ァィゥェォッャュョ → アイウエオツヤユヨ).

    Args:
        text: Input text containing small-form kana characters.

    Returns:
        Text with small kana expanded to normal size.
    """
    return jaconv.enlarge_smallkana(text)
