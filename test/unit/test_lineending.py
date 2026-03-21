"""Tests for line-ending conversion (F-04, F-05, F-06)."""

from press.transforms.lineending import to_cr, to_crlf, to_lf


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
