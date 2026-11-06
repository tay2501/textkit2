"""Tests for the ``press date`` / ``press time`` CLI commands."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

from press.__main__ import make_parser

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture(autouse=True)
def _appdata(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point %APPDATA% at an empty directory so the user's config is never read."""
    monkeypatch.setenv("APPDATA", str(tmp_path))
    return tmp_path


def _write_config(appdata: Path, body: str) -> None:
    press = appdata / "press"
    press.mkdir(exist_ok=True)
    (press / "config.toml").write_text(body, encoding="utf-8")


def _run(*argv: str) -> int:
    parser = make_parser()
    args = parser.parse_args(list(argv))
    return int(args.func(args))


class TestDefaults:
    def test_date_prints_yyyymmdd(self, capsys: pytest.CaptureFixture[str]) -> None:
        assert _run("date") == 0
        assert re.fullmatch(r"\d{8}\n", capsys.readouterr().out)

    def test_time_prints_hhmmss(self, capsys: pytest.CaptureFixture[str]) -> None:
        assert _run("time") == 0
        assert re.fullmatch(r"\d{6}\n", capsys.readouterr().out)

    def test_dt_alias(self, capsys: pytest.CaptureFixture[str]) -> None:
        assert _run("dt") == 0
        assert re.fullmatch(r"\d{8}\n", capsys.readouterr().out)


class TestFormat:
    def test_plus_format_overrides(self, capsys: pytest.CaptureFixture[str]) -> None:
        assert _run("date", "+%Y-%m-%d") == 0
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}\n", capsys.readouterr().out)

    def test_config_format_is_used(
        self, _appdata: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _write_config(_appdata, '[date]\nformat = "%Y-%m-%d"\n[time]\nformat = "%H:%M"\n')
        _run("date")
        _run("time")
        date_line, time_line = capsys.readouterr().out.splitlines()
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", date_line)
        assert re.fullmatch(r"\d{2}:\d{2}", time_line)

    def test_plus_format_beats_config(
        self, _appdata: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _write_config(_appdata, '[date]\nformat = "%Y-%m-%d"\n')
        _run("date", "+%Y")
        assert re.fullmatch(r"\d{4}\n", capsys.readouterr().out)

    def test_plus_format_skips_a_broken_config(
        self, _appdata: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """An explicit +FORMAT must not depend on config.toml at all."""
        _write_config(_appdata, "this is [not toml")
        assert _run("date", "+%Y") == 0
        assert re.fullmatch(r"\d{4}\n", capsys.readouterr().out)

    def test_format_without_plus_is_an_error(self, capsys: pytest.CaptureFixture[str]) -> None:
        assert _run("date", "%Y") == 1
        assert "must start with '+'" in capsys.readouterr().err

    def test_empty_plus_format_is_an_error(self, capsys: pytest.CaptureFixture[str]) -> None:
        assert _run("date", "+") == 1
        assert "empty" in capsys.readouterr().err

    def test_invalid_config_reports_and_fails(
        self, _appdata: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _write_config(_appdata, '[date]\nformat = ""\n')
        assert _run("date") == 1
        captured = capsys.readouterr()
        assert captured.out == ""
        assert "press date: error: [date] format in config.toml: format is empty" in captured.err

    def test_bad_date_format_does_not_break_time(
        self, _appdata: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A broken [date] key is scoped to date, not to every config reader."""
        _write_config(_appdata, '[date]\nformat = ""\n')
        assert _run("time") == 0
        assert re.fullmatch(r"\d{6}\n", capsys.readouterr().out)

    def test_quiet_suppresses_the_error(
        self, _appdata: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _write_config(_appdata, '[date]\nformat = ""\n')
        assert _run("date", "-q") == 1
        assert capsys.readouterr().err == ""


class TestUtc:
    def test_utc_flag_is_forwarded(self, capsys: pytest.CaptureFixture[str]) -> None:
        with patch("press.clock.format_now", return_value="X") as mock_fmt:
            assert _run("time", "-u") == 0
        assert mock_fmt.call_args.kwargs == {"utc": True}
        assert capsys.readouterr().out == "X\n"

    def test_local_time_by_default(self) -> None:
        with patch("press.clock.format_now", return_value="X") as mock_fmt:
            _run("date", "--quiet")
        assert mock_fmt.call_args.args == ("%Y%m%d",)
        assert mock_fmt.call_args.kwargs == {"utc": False}


class TestCopy:
    def test_copy_writes_value_without_newline_and_snapshots_undo(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        with (
            patch("press.clock.format_now", return_value="20261106"),
            patch("press._cli_helpers._snapshot_clipboard_for_undo") as mock_snap,
            patch("press.clipboard.set_clipboard_text") as mock_set,
        ):
            assert _run("date", "-C") == 0
        mock_snap.assert_called_once()
        mock_set.assert_called_once_with("20261106", sensitive=False)
        assert capsys.readouterr().out == "20261106\n"

    def test_clipboard_failure_is_a_warning(self, capsys: pytest.CaptureFixture[str]) -> None:
        with (
            patch("press._cli_helpers._snapshot_clipboard_for_undo"),
            patch("press.clipboard.set_clipboard_text", side_effect=OSError("busy")),
        ):
            assert _run("time", "-C") == 0
        assert "warning: clipboard write failed" in capsys.readouterr().err

    def test_no_clipboard_access_without_copy(self) -> None:
        with patch("press.clipboard.set_clipboard_text") as mock_set:
            _run("date")
        mock_set.assert_not_called()
