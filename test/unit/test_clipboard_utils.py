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


class TestHoldStub:
    def test_hold_exits_one(self) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "press", "hold"],
            capture_output=True,
            text=True,
            env={**__import__("os").environ, "PYTHONUTF8": "1"},
        )
        assert result.returncode == 1
        assert "not yet implemented" in result.stderr
