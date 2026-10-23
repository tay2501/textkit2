"""Tests for press._cli_helpers — the shared read → transform → write runner."""

from __future__ import annotations

import argparse
from unittest.mock import patch

import pytest

from press._cli_helpers import _run_transform


def _args(**overrides: object) -> argparse.Namespace:
    defaults: dict[str, object] = {
        "command": "upper",
        "from_clipboard": False,
        "copy": True,
        "input": "abc",
        "quiet": False,
        "verbose": False,
        "fallback": False,
    }
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


class TestIoFlags:
    """Clipboard flags follow pbcopy/pbpaste wording, not a case-only pair."""

    def _parse(self, *argv: str) -> argparse.Namespace:
        from press.__main__ import make_parser

        return make_parser().parse_args(["upper", *argv])

    @pytest.mark.parametrize("flag", ["-C", "--copy"])
    def test_copy_writes_the_clipboard(self, flag: str) -> None:
        assert self._parse(flag).copy is True

    def test_from_clipboard_reads_the_clipboard(self) -> None:
        assert self._parse("--from-clipboard").from_clipboard is True

    @pytest.mark.parametrize("old", ["-c", "--clip-in", "--clip-out"])
    def test_old_flags_are_gone(self, old: str) -> None:
        with pytest.raises(SystemExit) as exc:
            self._parse(old)
        assert exc.value.code == 2

    def test_long_option_prefixes_are_rejected_in_subcommands(self) -> None:
        # allow_abbrev must reach every subparser, not only the root one.
        with pytest.raises(SystemExit) as exc:
            self._parse("--cop")
        assert exc.value.code == 2

    def test_short_flags_still_combine(self) -> None:
        args = self._parse("-Cq")
        assert args.copy is True
        assert args.quiet is True


class TestClipboardWriteFailure:
    """A failed ``-C`` clipboard write is a reported error, never a traceback."""

    @pytest.fixture(autouse=True)
    def _no_undo_snapshot(self) -> object:
        with patch("press._cli_helpers._snapshot_clipboard_for_undo"):
            yield

    def test_clipboard_write_failure_exits_1(self, capsys: pytest.CaptureFixture[str]) -> None:
        with patch(
            "press.clipboard.set_clipboard_text",
            side_effect=RuntimeError("Failed to open clipboard"),
        ):
            code = _run_transform(str.upper, _args())

        assert code == 1
        captured = capsys.readouterr()
        assert captured.out == "ABC"  # stdout was already delivered
        assert captured.err == "press upper: error: Failed to open clipboard\n"

    def test_fallback_clipboard_write_failure_exits_1(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        def _boom(_text: str) -> str:
            raise ValueError("bad input")

        with patch(
            "press.clipboard.set_clipboard_text",
            side_effect=RuntimeError("Failed to open clipboard"),
        ):
            code = _run_transform(_boom, _args(fallback=True))

        assert code == 1
        assert "press upper: error: Failed to open clipboard" in capsys.readouterr().err

    def test_quiet_suppresses_clipboard_write_error(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        with patch(
            "press.clipboard.set_clipboard_text",
            side_effect=OSError("Clipboard access is only supported on Windows"),
        ):
            code = _run_transform(str.upper, _args(quiet=True))

        assert code == 1
        assert capsys.readouterr().err == ""
