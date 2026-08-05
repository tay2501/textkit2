"""Unit tests for the `press trace on|off|status` CLI command group."""

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


class TestTraceOn:
    def test_creates_marker_file(self, tmp_path: Path) -> None:
        marker = tmp_path / "trace"
        with patch("press._paths.trace_path", return_value=marker):
            assert _run_cli(["trace", "on"]) == 0
        assert marker.exists()

    def test_prints_confirmation(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        marker = tmp_path / "trace"
        with patch("press._paths.trace_path", return_value=marker):
            assert _run_cli(["trace", "on"]) == 0
        out = capsys.readouterr().out
        assert "ON" in out

    def test_idempotent_when_already_on(self, tmp_path: Path) -> None:
        marker = tmp_path / "trace"
        marker.touch()
        with patch("press._paths.trace_path", return_value=marker):
            assert _run_cli(["trace", "on"]) == 0
        assert marker.exists()


class TestTraceOff:
    def test_removes_marker_file(self, tmp_path: Path) -> None:
        marker = tmp_path / "trace"
        marker.touch()
        with patch("press._paths.trace_path", return_value=marker):
            assert _run_cli(["trace", "off"]) == 0
        assert not marker.exists()

    def test_safe_when_marker_absent(self, tmp_path: Path) -> None:
        marker = tmp_path / "trace"
        with patch("press._paths.trace_path", return_value=marker):
            assert _run_cli(["trace", "off"]) == 0
        assert not marker.exists()

    def test_prints_confirmation(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        marker = tmp_path / "trace"
        with patch("press._paths.trace_path", return_value=marker):
            assert _run_cli(["trace", "off"]) == 0
        out = capsys.readouterr().out
        assert "OFF" in out


class TestTraceStatus:
    def test_reports_on_when_marker_exists(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        marker = tmp_path / "trace"
        marker.touch()
        with patch("press._paths.trace_path", return_value=marker):
            assert _run_cli(["trace", "status"]) == 0
        assert "ON" in capsys.readouterr().out

    def test_reports_off_when_marker_absent(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        marker = tmp_path / "trace"
        with patch("press._paths.trace_path", return_value=marker):
            assert _run_cli(["trace", "status"]) == 0
        assert "OFF" in capsys.readouterr().out


class TestTraceNoAction:
    def test_no_subcommand_returns_zero(self) -> None:
        with patch("subprocess.run"):
            assert _run_cli(["trace"]) == 0
