"""Tests for Unicode escape / HTML entity conversion (F-11, F-12)."""

import pytest

from press.transforms.escape import (
    decode_html_entities,
    decode_unicode_escape,
    encode_unicode_escape,
)


class TestEncodeUnicodeEscape:
    def test_japanese(self) -> None:
        assert encode_unicode_escape("テスト") == r"\u30c6\u30b9\u30c8"

    def test_ascii_unchanged(self) -> None:
        # ASCII chars are represented as-is (not escaped)
        result = encode_unicode_escape("ABC")
        assert result == "ABC"

    def test_empty(self) -> None:
        assert encode_unicode_escape("") == ""

    def test_mixed(self) -> None:
        result = encode_unicode_escape("A テ")
        assert r"\u30c6" in result
        assert "A" in result


class TestDecodeUnicodeEscape:
    def test_basic(self) -> None:
        assert decode_unicode_escape(r"\u30c6\u30b9\u30c8") == "テスト"

    def test_ascii_passthrough(self) -> None:
        assert decode_unicode_escape("ABC") == "ABC"

    def test_empty(self) -> None:
        assert decode_unicode_escape("") == ""

    def test_invalid_raises(self) -> None:
        with pytest.raises((ValueError, UnicodeDecodeError)):
            decode_unicode_escape(r"\uZZZZ")

    def test_roundtrip(self) -> None:
        original = "テスト ABC 123"
        assert decode_unicode_escape(encode_unicode_escape(original)) == original


class TestDecodeHtmlEntities:
    def test_lt_gt(self) -> None:
        assert decode_html_entities("&lt;div&gt;") == "<div>"

    def test_amp(self) -> None:
        assert decode_html_entities("&amp;") == "&"

    def test_numeric_hex(self) -> None:
        assert decode_html_entities("&#x3042;") == "あ"

    def test_numeric_decimal(self) -> None:
        assert decode_html_entities("&#12354;") == "あ"

    def test_no_entities(self) -> None:
        assert decode_html_entities("plain text") == "plain text"

    def test_empty(self) -> None:
        assert decode_html_entities("") == ""
