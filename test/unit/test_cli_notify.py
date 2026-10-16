"""Unit tests for the `press notify off|on|status` CLI command group.

``off`` and ``on`` are deliberately *not* a toggle: during a screen share the
user may run ``off`` two or three times to be sure, and every run must leave
notifications off.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


def _run_cli(argv: list[str]) -> int:
    from press.__main__ import make_parser

    args = make_parser().parse_args(argv)
    return int(args.func(args))


class TestNotifyOff:
    def test_creates_marker_file(self, tmp_path: Path) -> None:
        marker = tmp_path / "notify-off"
        with patch("press._paths.notify_off_path", return_value=marker):
            assert _run_cli(["notify", "off"]) == 0
        assert marker.exists()

    def test_repeating_off_stays_off(self, tmp_path: Path) -> None:
        marker = tmp_path / "notify-off"
        with patch("press._paths.notify_off_path", return_value=marker):
            for _ in range(3):
                assert _run_cli(["notify", "off"]) == 0
        assert marker.exists()

    def test_creates_missing_parent_directory(self, tmp_path: Path) -> None:
        marker = tmp_path / "fresh" / "notify-off"
        with patch("press._paths.notify_off_path", return_value=marker):
            assert _run_cli(["notify", "off"]) == 0
        assert marker.exists()

    def test_prints_state(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        with patch("press._paths.notify_off_path", return_value=tmp_path / "notify-off"):
            _run_cli(["notify", "off"])
        assert capsys.readouterr().out == "press notify: OFF\n"


class TestNotifyOn:
    def test_removes_marker_file(self, tmp_path: Path) -> None:
        marker = tmp_path / "notify-off"
        marker.touch()
        with patch("press._paths.notify_off_path", return_value=marker):
            assert _run_cli(["notify", "on"]) == 0
        assert not marker.exists()

    def test_repeating_on_stays_on(self, tmp_path: Path) -> None:
        marker = tmp_path / "notify-off"
        with patch("press._paths.notify_off_path", return_value=marker):
            for _ in range(3):
                assert _run_cli(["notify", "on"]) == 0
        assert not marker.exists()

    def test_prints_state(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        with patch("press._paths.notify_off_path", return_value=tmp_path / "notify-off"):
            _run_cli(["notify", "on"])
        assert capsys.readouterr().out == "press notify: ON\n"


class TestNotifyStatus:
    def test_reports_off(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        marker = tmp_path / "notify-off"
        marker.touch()
        with patch("press._paths.notify_off_path", return_value=marker):
            assert _run_cli(["notify", "status"]) == 0
        assert capsys.readouterr().out == "press notify: OFF\n"

    def test_reports_on(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        with patch("press._paths.notify_off_path", return_value=tmp_path / "notify-off"):
            assert _run_cli(["notify", "status"]) == 0
        assert capsys.readouterr().out == "press notify: ON\n"


class TestNotifyWithoutAction:
    def test_prints_help(self, capsys: pytest.CaptureFixture[str]) -> None:
        assert _run_cli(["notify"]) == 0
        assert "usage: " in capsys.readouterr().out
