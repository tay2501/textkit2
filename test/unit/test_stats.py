"""Tests for the text statistics report (count command)."""

from press.transforms.stats import count_text


def _parse(report: str) -> dict[str, int]:
    return {line.split()[0]: int(line.split()[1]) for line in report.splitlines()}


class TestCountText:
    def test_empty(self) -> None:
        stats = _parse(count_text(""))
        assert stats == {"chars": 0, "non-space": 0, "words": 0, "lines": 0, "bytes-utf8": 0}

    def test_ascii_words(self) -> None:
        stats = _parse(count_text("hello world"))
        assert stats["chars"] == 11
        assert stats["non-space"] == 10
        assert stats["words"] == 2
        assert stats["lines"] == 1
        assert stats["bytes-utf8"] == 11

    def test_multiline(self) -> None:
        stats = _parse(count_text("a\nb\nc\n"))
        assert stats["lines"] == 3
        assert stats["words"] == 3

    def test_japanese_bytes(self) -> None:
        # "あ" is 3 bytes in UTF-8; no spaces → non-space equals chars
        stats = _parse(count_text("あいう"))
        assert stats["chars"] == 3
        assert stats["non-space"] == 3
        assert stats["bytes-utf8"] == 9

    def test_fullwidth_space_is_whitespace(self) -> None:
        stats = _parse(count_text("あ　い"))
        assert stats["chars"] == 3
        assert stats["non-space"] == 2

    def test_report_ends_with_newline(self) -> None:
        assert count_text("x").endswith("\n")
