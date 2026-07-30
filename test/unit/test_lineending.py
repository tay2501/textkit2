"""Tests for line-ending conversion (F-04, F-05, F-06)."""

from press.transforms.lineending import strip_newlines, to_cr, to_crlf, to_lf


class TestToCrlf:
    def test_lf_to_crlf(self) -> None:
        assert to_crlf("a\nb\nc") == "a\r\nb\r\nc"

    def test_cr_to_crlf(self) -> None:
        assert to_crlf("a\rb\rc") == "a\r\nb\r\nc"

    def test_already_crlf(self) -> None:
        assert to_crlf("a\r\nb") == "a\r\nb"

    def test_mixed(self) -> None:
        assert to_crlf("a\nb\r\nc\rd") == "a\r\nb\r\nc\r\nd"

    def test_empty(self) -> None:
        assert to_crlf("") == ""

    def test_no_newline(self) -> None:
        assert to_crlf("hello") == "hello"


class TestToLf:
    def test_crlf_to_lf(self) -> None:
        assert to_lf("a\r\nb\r\nc") == "a\nb\nc"

    def test_cr_to_lf(self) -> None:
        assert to_lf("a\rb\rc") == "a\nb\nc"

    def test_already_lf(self) -> None:
        assert to_lf("a\nb") == "a\nb"

    def test_mixed(self) -> None:
        assert to_lf("a\nb\r\nc\rd") == "a\nb\nc\nd"

    def test_empty(self) -> None:
        assert to_lf("") == ""


class TestToCr:
    def test_lf_to_cr(self) -> None:
        assert to_cr("a\nb\nc") == "a\rb\rc"

    def test_crlf_to_cr(self) -> None:
        assert to_cr("a\r\nb") == "a\rb"

    def test_already_cr(self) -> None:
        assert to_cr("a\rb") == "a\rb"

    def test_empty(self) -> None:
        assert to_cr("") == ""


class TestStripNewlines:
    """The contract: no U+000A and no U+000D survive, and nothing else changes."""

    def test_lf_removed(self) -> None:
        assert strip_newlines("a\nb\nc") == "abc"

    def test_crlf_counts_as_one_break(self) -> None:
        assert strip_newlines("a\r\nb") == "ab"

    def test_cr_removed(self) -> None:
        assert strip_newlines("a\rb") == "ab"

    def test_mixed_endings(self) -> None:
        assert strip_newlines("a\nb\r\nc\rd") == "abcd"

    def test_lf_then_cr_is_two_breaks(self) -> None:
        assert strip_newlines("a\n\rb") == "ab"

    def test_blank_lines_removed(self) -> None:
        assert strip_newlines("a\n\n\nb") == "ab"

    def test_trailing_newline_removed(self) -> None:
        # Unlike the line-oriented transforms, which preserve it on purpose.
        assert strip_newlines("a\nb\n") == "ab"

    def test_only_newlines(self) -> None:
        assert strip_newlines("\r\n\n\r") == ""

    def test_empty(self) -> None:
        assert strip_newlines("") == ""

    def test_no_newline_unchanged(self) -> None:
        assert strip_newlines("hello") == "hello"

    def test_japanese_joins_without_a_separator(self) -> None:
        assert strip_newlines("研究\n開発") == "研究開発"

    def test_english_words_run_together(self) -> None:
        # Documented consequence of "remove, insert nothing" — not a bug.
        assert strip_newlines("hello\nworld") == "helloworld"

    def test_surrounding_spaces_preserved(self) -> None:
        assert strip_newlines("a \n b") == "a  b"

    def test_unicode_line_separator_is_not_a_line_ending(self) -> None:
        # to_lf defines line endings as CR/LF for the whole package.
        assert strip_newlines("a\u2028b\u2029c") == "a\u2028b\u2029c"

    def test_idempotent(self) -> None:
        once = strip_newlines("a\r\nb\nc")
        assert strip_newlines(once) == once

    def test_output_contains_no_line_ending(self) -> None:
        result = strip_newlines("a\r\nb\rc\nd\n")
        assert "\r" not in result
        assert "\n" not in result
