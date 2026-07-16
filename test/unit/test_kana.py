"""Tests for hiragana / katakana conversion."""

from press.transforms.kana import to_hiragana, to_katakana


class TestToKatakana:
    def test_basic(self) -> None:
        assert to_katakana("ひらがな") == "ヒラガナ"

    def test_mixed_text_preserved(self) -> None:
        assert to_katakana("ABC123 かな カナ 漢字") == "ABC123 カナ カナ 漢字"

    def test_small_kana(self) -> None:
        assert to_katakana("きょう、ちょっと") == "キョウ、チョット"

    def test_voiced_marks(self) -> None:
        assert to_katakana("ばぱ") == "バパ"

    def test_no_hiragana_unchanged(self) -> None:
        assert to_katakana("KATAKANA text") == "KATAKANA text"

    def test_empty(self) -> None:
        assert to_katakana("") == ""


class TestToHiragana:
    def test_basic(self) -> None:
        assert to_hiragana("カタカナ") == "かたかな"

    def test_mixed_text_preserved(self) -> None:
        assert to_hiragana("ABC123 カナ 漢字") == "ABC123 かな 漢字"

    def test_small_kana(self) -> None:
        assert to_hiragana("キョウ、チョット") == "きょう、ちょっと"

    def test_roundtrip(self) -> None:
        assert to_hiragana(to_katakana("あいうえお")) == "あいうえお"

    def test_empty(self) -> None:
        assert to_hiragana("") == ""
