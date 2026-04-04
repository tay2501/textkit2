"""Tests for clipboard utility commands (clear, hold)."""

import subprocess
import sys

import pytest


@pytest.mark.windows_only
class TestClearClipboard:
    def test_clear_exits_zero(self) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "press", "clear"],
            capture_output=True,
            text=True,
            env={**__import__("os").environ, "PYTHONUTF8": "1"},
        )
        assert result.returncode == 0

    def test_alias_cl(self) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "press", "cl"],
            capture_output=True,
            text=True,
            env={**__import__("os").environ, "PYTHONUTF8": "1"},
        )
        assert result.returncode == 0

    def test_clear_quiet_suppresses_stderr(self) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "press", "clear", "-q"],
            capture_output=True,
            text=True,
            env={**__import__("os").environ, "PYTHONUTF8": "1"},
        )
        assert result.returncode == 0
        assert result.stderr == ""


@pytest.mark.windows_only
class TestHoldCommand:
    def _seed_clipboard(self, text: str) -> None:
        """Put *text* into the clipboard so hold has something to save."""
        result = subprocess.run(
            [sys.executable, "-c", f"import press.clipboard as c; c.set_clipboard_text({text!r})"],
            capture_output=True,
            text=True,
            env={**__import__("os").environ, "PYTHONUTF8": "1"},
        )
        assert result.returncode == 0, result.stderr

    def test_hold_prints_held_to_stderr(self) -> None:
        """hold with non-empty clipboard prints 'press hold: held' to stderr."""
        self._seed_clipboard("test hold content")
        result = subprocess.run(
            [sys.executable, "-m", "press", "hold"],
            capture_output=True,
            text=True,
            env={**__import__("os").environ, "PYTHONUTF8": "1"},
        )
        assert result.returncode == 0
        assert "press hold:" in result.stderr

    def test_hold_quiet_suppresses_stderr(self) -> None:
        self._seed_clipboard("test hold quiet")
        result = subprocess.run(
            [sys.executable, "-m", "press", "hold", "-q"],
            capture_output=True,
            text=True,
            env={**__import__("os").environ, "PYTHONUTF8": "1"},
        )
        assert result.returncode == 0
        assert result.stderr == ""
