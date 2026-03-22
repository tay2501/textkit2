"""Tests for full-width / half-width conversion (F-01, F-02)."""

from press.transforms.width import to_fullwidth, to_halfwidth


class TestToHalfwidth:
    def test_ascii_fullwidth_letters(self) -> None:
        assert to_halfwidth("ＡＢＣＤ") == "ABCD"

    def test_ascii_fullwidth_digits(self) -> None:
        assert to_halfwidth("１２３") == "123"

    def test_fullwidth_space(self) -> None:
        assert to_halfwidth("　") == " "

    def test_mixed(self) -> None:
        assert to_halfwidth("ＴＡＢＬＥ１　") == "TABLE1 "

    def test_already_halfwidth(self) -> None:
        assert to_halfwidth("ABC123") == "ABC123"

    def test_empty(self) -> None:
        assert to_halfwidth("") == ""

    def test_katakana_stays(self) -> None:
        # Katakana fullwidth → halfwidth (jaconv converts these)
        result = to_halfwidth("テスト")
        assert result == "ﾃｽﾄ"

    def test_preserves_hiragana(self) -> None:
        # Hiragana is not converted by halfwidth
        result = to_halfwidth("てすと")
        assert result == "てすと"

    def test_multiline(self) -> None:
        assert to_halfwidth("ＡＢＣ\nＤＥＦ") == "ABC\nDEF"


class TestToFullwidth:
    def test_ascii_letters(self) -> None:
        assert to_fullwidth("ABCD") == "ＡＢＣＤ"

    def test_ascii_digits(self) -> None:
        assert to_fullwidth("123") == "１２３"

    def test_space(self) -> None:
        assert to_fullwidth(" ") == "　"

    def test_already_fullwidth(self) -> None:
        assert to_fullwidth("ＡＢＣＤ") == "ＡＢＣＤ"

    def test_empty(self) -> None:
        assert to_fullwidth("") == ""
