"""Tests for press.clock — current date/time formatting (date/time commands)."""

from __future__ import annotations

import sys
from datetime import UTC, datetime, timedelta, timezone

import pytest

from press.clock import (
    DEFAULT_DATE_FORMAT,
    DEFAULT_TIME_FORMAT,
    check_format,
    format_configured,
    format_now,
)

JST = timezone(timedelta(hours=9))
NOW = datetime(2026, 11, 6, 9, 5, 7, tzinfo=JST)


class TestFormatNow:
    def test_default_date_format_is_yyyymmdd(self) -> None:
        assert format_now(DEFAULT_DATE_FORMAT, now=NOW) == "20261106"

    def test_default_time_format_is_hhmmss(self) -> None:
        assert format_now(DEFAULT_TIME_FORMAT, now=NOW) == "090507"

    @pytest.mark.parametrize(
        ("fmt", "expected"),
        [
            ("%Y-%m-%d", "2026-11-06"),
            ("%Y/%m/%d", "2026/11/06"),
            ("%H:%M:%S", "09:05:07"),
            ("%Y-%m-%dT%H:%M:%S%z", "2026-11-06T09:05:07+0900"),
            ("100%%", "100%"),
        ],
    )
    def test_strftime_formats(self, fmt: str, expected: str) -> None:
        assert format_now(fmt, now=NOW) == expected

    def test_non_ascii_literals_survive(self) -> None:
        """Japanese date formats must not be mangled by the C runtime."""
        assert format_now("%Y年%m月%d日", now=NOW) == "2026年11月06日"

    def test_utc_converts_an_aware_now(self) -> None:
        assert format_now("%Y%m%d %H%M%S", utc=True, now=NOW) == "20261106 000507"

    def test_utc_crosses_the_date_line(self) -> None:
        early = datetime(2026, 11, 6, 3, 0, tzinfo=JST)
        assert format_now("%Y%m%d", utc=True, now=early) == "20261105"

    def test_without_now_uses_the_current_local_time(self) -> None:
        before = datetime.now().astimezone()
        result = format_now("%Y%m%d")
        after = datetime.now().astimezone()
        assert result in {before.strftime("%Y%m%d"), after.strftime("%Y%m%d")}

    def test_without_now_utc_uses_the_current_utc_time(self) -> None:
        before = datetime.now(UTC)
        result = format_now("%Y%m%d%H", utc=True)
        after = datetime.now(UTC)
        assert result in {before.strftime("%Y%m%d%H"), after.strftime("%Y%m%d%H")}

    def test_invalid_format_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="format"):
            format_now("", now=NOW)


class TestFormatConfigured:
    def test_valid_format_is_formatted(self) -> None:
        assert len(format_configured("date", "%Y")) == 4

    def test_error_names_the_config_key(self) -> None:
        with pytest.raises(ValueError, match=r"^\[time\] format in config\.toml: format is empty"):
            format_configured("time", "")


class TestCheckFormat:
    @pytest.mark.parametrize("fmt", ["%Y%m%d", "%H%M%S", "%Y-%m-%d", "%Y年%m月%d日"])
    def test_valid_formats_are_returned(self, fmt: str) -> None:
        assert check_format(fmt) == fmt

    def test_empty_format_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="empty"):
            check_format("")

    @pytest.mark.parametrize("value", [20261106, None, ["%Y"]])
    def test_non_string_is_rejected(self, value: object) -> None:
        with pytest.raises(ValueError, match="string"):
            check_format(value)

    def test_nul_is_rejected(self) -> None:
        """CF_UNICODETEXT stops at NUL, so the clipboard would differ from stdout."""
        with pytest.raises(ValueError, match="NUL"):
            check_format("a\0b")

    def test_literal_only_format_is_allowed(self) -> None:
        """A format without directives is odd but well-defined — not an error."""
        assert check_format("today") == "today"

    @pytest.mark.skipif(sys.platform != "win32", reason="glibc accepts unknown directives")
    @pytest.mark.parametrize("fmt", ["%Q", "%-d", "%Y%"])
    def test_directives_the_platform_rejects(self, fmt: str) -> None:
        with pytest.raises(ValueError, match="invalid format"):
            check_format(fmt)
