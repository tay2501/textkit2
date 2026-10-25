"""Tests for clipboard utility commands (clear, stash)."""

from __future__ import annotations

import subprocess
import sys
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path


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
class TestStashCommand:
    """End-to-end: the real clipboard and a real (isolated) stash file."""

    def _press(self, appdata: str, *argv: str) -> subprocess.CompletedProcess[str]:
        env = {**__import__("os").environ, "PYTHONUTF8": "1", "APPDATA": appdata}
        return subprocess.run(
            [sys.executable, *argv], capture_output=True, text=True, env=env, check=False
        )

    def test_push_pop_round_trip(self, tmp_path: Path) -> None:
        appdata = str(tmp_path)
        seed = "import press.clipboard as c; c.set_clipboard_text('stash e2e')"
        assert self._press(appdata, "-c", seed).returncode == 0

        pushed = self._press(appdata, "-m", "press", "stash", "push")
        assert pushed.returncode == 0, pushed.stderr
        assert "press stash:" in pushed.stderr

        popped = self._press(appdata, "-m", "press", "stash", "pop", "-q")
        assert popped.returncode == 0, popped.stderr
        assert popped.stderr == ""
