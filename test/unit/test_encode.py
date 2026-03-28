"""Tests for encode/decode transforms (F-17 to F-20)."""

import pytest

from press.transforms.encode import base64_decode, base64_encode, url_decode, url_encode


class TestBase64Encode:
    def test_hello(self) -> None:
        assert base64_encode("hello") == "aGVsbG8="

    def test_hello_world(self) -> None:
        assert base64_encode("hello world") == "aGVsbG8gd29ybGQ="

    def test_empty(self) -> None:
        assert base64_encode("") == ""

    def test_japanese(self) -> None:
        assert base64_encode("こんにちは") == "44GT44KT44Gr44Gh44Gv"

    def test_no_trailing_newline(self) -> None:
        result = base64_encode("hello")
        assert not result.endswith("\n")

    def test_roundtrip(self) -> None:
        original = "Hello, World! テスト"
        assert base64_decode(base64_encode(original)) == original


class TestBase64Decode:
    def test_hello(self) -> None:
        assert base64_decode("aGVsbG8=") == "hello"

    def test_hello_world(self) -> None:
        assert base64_decode("aGVsbG8gd29ybGQ=") == "hello world"

    def test_empty(self) -> None:
        assert base64_decode("") == ""

    def test_japanese(self) -> None:
        assert base64_decode("44GT44KT44Gr44Gh44Gv") == "こんにちは"

    def test_invalid_raises_value_error(self) -> None:
        with pytest.raises(ValueError):
            base64_decode("invalid base64!!!")

    def test_non_utf8_raises_value_error(self) -> None:
        # Valid base64 but decoded bytes are not valid UTF-8
        import base64 as _b64

        bad_bytes = _b64.b64encode(b"\xff\xfe")
        with pytest.raises(ValueError):
            base64_decode(bad_bytes.decode("ascii"))


class TestUrlEncode:
    def test_space(self) -> None:
        assert url_encode("hello world") == "hello%20world"

    def test_special_chars(self) -> None:
        assert url_encode("a=b&c=d") == "a%3Db%26c%3Dd"

    def test_empty(self) -> None:
        assert url_encode("") == ""

    def test_japanese(self) -> None:
        result = url_encode("あ")
        assert result == "%E3%81%82"

    def test_safe_chars_encoded(self) -> None:
        # safe='' means even / and @ are encoded
        assert "/" not in url_encode("a/b")
        assert "@" not in url_encode("a@b")

    def test_roundtrip(self) -> None:
        original = "hello world / テスト"
        assert url_decode(url_encode(original)) == original


class TestUrlDecode:
    def test_space(self) -> None:
        assert url_decode("hello%20world") == "hello world"

    def test_special_chars(self) -> None:
        assert url_decode("a%3Db%26c%3Dd") == "a=b&c=d"

    def test_empty(self) -> None:
        assert url_decode("") == ""

    def test_japanese(self) -> None:
        assert url_decode("%E3%81%82") == "あ"

    def test_plus_not_space(self) -> None:
        # urllib.parse.unquote does NOT convert + to space (unlike unquote_plus)
        assert url_decode("hello+world") == "hello+world"
