"""Tests for Unix time ⇔ ISO 8601 date conversion."""

from datetime import datetime

import pytest

from press.transforms.timestamp import date_to_unix, unix_to_date

# 2025-07-17T00:00:00+00:00
EPOCH_2025_07_17 = 1752710400


class TestUnixToDate:
    def test_epoch_zero_utc(self) -> None:
        assert unix_to_date("0", utc=True) == "1970-01-01T00:00:00+00:00"

    def test_known_value_utc(self) -> None:
        assert unix_to_date(str(EPOCH_2025_07_17), utc=True) == "2025-07-17T00:00:00+00:00"

    def test_milliseconds_auto_detected(self) -> None:
        result = unix_to_date(f"{EPOCH_2025_07_17}123", utc=True)
        assert result == "2025-07-17T00:00:00.123+00:00"

    def test_local_output_has_offset(self) -> None:
        result = unix_to_date(str(EPOCH_2025_07_17))
        # Local time still carries an explicit UTC offset
        assert "+" in result or "-" in result[10:]

    def test_multiline_blank_lines_pass_through(self) -> None:
        result = unix_to_date("0\n\n86400\n", utc=True)
        assert result == "1970-01-01T00:00:00+00:00\n\n1970-01-02T00:00:00+00:00\n"

    def test_surrounding_whitespace_tolerated(self) -> None:
        assert unix_to_date("  0  ", utc=True) == "1970-01-01T00:00:00+00:00"

    def test_invalid_raises(self) -> None:
        with pytest.raises(ValueError, match="not a unix timestamp"):
            unix_to_date("yesterday")


class TestDateToUnix:
    def test_utc_offset(self) -> None:
        assert date_to_unix("2025-07-17T00:00:00+00:00") == str(EPOCH_2025_07_17)

    def test_z_suffix(self) -> None:
        assert date_to_unix("2025-07-17T00:00:00Z") == str(EPOCH_2025_07_17)

    def test_space_separator(self) -> None:
        assert date_to_unix("2025-07-17 00:00:00+00:00") == str(EPOCH_2025_07_17)

    def test_naive_is_local_time(self) -> None:
        expected = int(datetime(2025, 7, 17).astimezone().timestamp())
        assert date_to_unix("2025-07-17T00:00:00") == str(expected)

    def test_ms_flag(self) -> None:
        assert date_to_unix("1970-01-01T00:00:00.500+00:00", ms=True) == "500"

    def test_fractional_seconds(self) -> None:
        assert date_to_unix("1970-01-01T00:00:00.500+00:00") == "0.5"

    def test_multiline(self) -> None:
        result = date_to_unix("1970-01-01T00:00:00Z\n1970-01-02T00:00:00Z")
        assert result == "0\n86400"

    def test_invalid_raises(self) -> None:
        with pytest.raises(ValueError, match="not an ISO 8601 date"):
            date_to_unix("not a date")

    def test_roundtrip_local(self) -> None:
        assert date_to_unix(unix_to_date(str(EPOCH_2025_07_17))) == str(EPOCH_2025_07_17)

    def test_roundtrip_utc(self) -> None:
        assert date_to_unix(unix_to_date("86400", utc=True)) == "86400"
