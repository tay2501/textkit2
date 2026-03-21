"""Tests for whitespace / line normalization (F-03)."""

from press.transforms.whitespace import normalize_whitespace


class TestNormalizeWhitespace:
    def test_leading_trailing_spaces(self) -> None:
        assert normalize_whitespace("  hello  ") == "hello"

    def test_multiple_spaces_collapsed(self) -> None:
        assert normalize_whitespace("a  b   c") == "a b c"

    def test_tabs_converted(self) -> None:
        assert normalize_whitespace("a\tb") == "a b"

    def test_fullwidth_space_removed(self) -> None:
        assert normalize_whitespace("　hello　") == "hello"

    def test_mixed_whitespace(self) -> None:
        assert normalize_whitespace("  　 USER_ID 　  ") == "USER_ID"

    def test_empty(self) -> None:
        assert normalize_whitespace("") == ""

    def test_only_whitespace(self) -> None:
        assert normalize_whitespace("   　   ") == ""

    def test_multiline_trimmed(self) -> None:
        # Each line is stripped, blank lines removed, rejoined
        result = normalize_whitespace("  line1  \n  line2  \n\n  line3  ")
        assert result == "line1\nline2\nline3"

    def test_crlf_treated_as_newline(self) -> None:
        result = normalize_whitespace("  a  \r\n  b  ")
        assert result == "a\nb"
