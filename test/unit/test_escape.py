"""Tests for Unicode escape / HTML entity conversion (F-11, F-12)."""

import pytest

from press.transforms.escape import (
    html_escape,
    html_unescape,
    unicode_escape,
    unicode_unescape,
)


class TestEncodeUnicodeEscape:
    def test_japanese(self) -> None:
        assert unicode_escape("テスト") == r"\u30c6\u30b9\u30c8"

    def test_ascii_unchanged(self) -> None:
        # ASCII chars are represented as-is (not escaped)
        result = unicode_escape("ABC")
        assert result == "ABC"

    def test_empty(self) -> None:
        assert unicode_escape("") == ""

    def test_mixed(self) -> None:
        result = unicode_escape("A テ")
        assert r"\u30c6" in result
        assert "A" in result


class TestDecodeUnicodeEscape:
    def test_basic(self) -> None:
        assert unicode_unescape(r"\u30c6\u30b9\u30c8") == "テスト"

    def test_ascii_passthrough(self) -> None:
        assert unicode_unescape("ABC") == "ABC"

    def test_empty(self) -> None:
        assert unicode_unescape("") == ""

    def test_invalid_raises(self) -> None:
        with pytest.raises((ValueError, UnicodeDecodeError)):
            unicode_unescape(r"\uZZZZ")

    def test_roundtrip(self) -> None:
        original = "テスト ABC 123"
        assert unicode_unescape(unicode_escape(original)) == original


class TestDecodeHtmlEntities:
    def test_lt_gt(self) -> None:
        assert html_unescape("&lt;div&gt;") == "<div>"

    def test_amp(self) -> None:
        assert html_unescape("&amp;") == "&"

    def test_numeric_hex(self) -> None:
        assert html_unescape("&#x3042;") == "あ"

    def test_numeric_decimal(self) -> None:
        assert html_unescape("&#12354;") == "あ"

    def test_no_entities(self) -> None:
        assert html_unescape("plain text") == "plain text"

    def test_empty(self) -> None:
        assert html_unescape("") == ""


class TestEncodeHtmlEntities:
    def test_lt_gt(self) -> None:
        assert html_escape("<div>") == "&lt;div&gt;"

    def test_amp(self) -> None:
        assert html_escape("a & b") == "a &amp; b"

    def test_quotes(self) -> None:
        assert html_escape("\"x\" 'y'") == "&quot;x&quot; &#x27;y&#x27;"

    def test_roundtrip(self) -> None:
        original = "<a href=\"?q=1&r=2\">'link'</a>"
        assert html_unescape(html_escape(original)) == original

    def test_plain_unchanged(self) -> None:
        assert html_escape("plain テキスト") == "plain テキスト"

    def test_empty(self) -> None:
        assert html_escape("") == ""
