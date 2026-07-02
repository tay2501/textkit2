"""Tests for platform-independent helpers in press.daemon.

These tests intentionally have NO windows_only marker so they run on Linux CI,
covering logic that does not depend on Win32 APIs (pystray, pywin32, ctypes).
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

# ---------------------------------------------------------------------------
# _to_pynput_hotkey (pure string transformation — no pynput at runtime)
# ---------------------------------------------------------------------------


class TestToPynputHotkey:
    @pytest.mark.parametrize(
        "press_spec,expected",
        [
            ("ctrl+shift+f10", "<ctrl>+<shift>+<f10>"),
            ("ctrl+alt+a", "<ctrl>+<alt>+a"),
            ("f12", "<f12>"),
            ("shift+u", "<shift>+u"),
            ("ctrl+shift+f1", "<ctrl>+<shift>+<f1>"),
            ("ctrl+shift+0", "<ctrl>+<shift>+0"),
            ("alt+f4", "<alt>+<f4>"),
            ("win+l", "<win>+l"),
        ],
    )
    def test_conversion(self, press_spec: str, expected: str) -> None:
        from press.daemon import _to_pynput_hotkey

        assert _to_pynput_hotkey(press_spec) == expected

    def test_single_char(self) -> None:
        from press.daemon import _to_pynput_hotkey

        assert _to_pynput_hotkey("a") == "a"

    def test_single_modifier(self) -> None:
        from press.daemon import _to_pynput_hotkey

        assert _to_pynput_hotkey("ctrl") == "<ctrl>"


# ---------------------------------------------------------------------------
# daemon_logs (file I/O only — no platform-specific dependencies)
# ---------------------------------------------------------------------------

_SAMPLE_LINES = [
    "2026-06-01T10:00:00 INFO     daemon started\n",
    "2026-06-01T10:00:01 DEBUG    registered hotkey ctrl+shift+0\n",
    "2026-06-01T10:01:00 WARNING  clipboard read failed\n",
    "2026-06-01T10:02:00 ERROR    transform error: json decode failed\n",
    "2026-06-01T10:03:00 INFO     command dispatched: halfwidth\n",
]


class TestDaemonLogsBasic:
    def _write_log(self, tmp_path: Path, lines: list[str]) -> Path:
        log_file = tmp_path / "daemon.log"
        log_file.write_text("".join(lines), encoding="utf-8")
        return log_file

    def test_missing_log_returns_1(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        monkeypatch.setattr("press.daemon._LOG_PATH", tmp_path / "daemon.log")
        from press.daemon import daemon_logs

        rc = daemon_logs()
        assert rc == 1
        assert "not found" in capsys.readouterr().err

    def test_all_lines_shown_by_default(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        log_file = self._write_log(tmp_path, _SAMPLE_LINES)
        monkeypatch.setattr("press.daemon._LOG_PATH", log_file)
        from press.daemon import daemon_logs

        rc = daemon_logs(lines=None, level="all")
        assert rc == 0
        out = capsys.readouterr().out
        assert "daemon started" in out
        assert "DEBUG" in out
        assert "WARNING" in out
        assert "ERROR" in out

    def test_tail_n_limits_output(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        log_file = self._write_log(tmp_path, _SAMPLE_LINES)
        monkeypatch.setattr("press.daemon._LOG_PATH", log_file)
        from press.daemon import daemon_logs

        rc = daemon_logs(lines=2, level="all")
        assert rc == 0
        out = capsys.readouterr().out.splitlines()
        assert len(out) == 2
        assert "transform error" in out[0]
        assert "command dispatched" in out[1]

    def test_level_filter_info_hides_debug(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        log_file = self._write_log(tmp_path, _SAMPLE_LINES)
        monkeypatch.setattr("press.daemon._LOG_PATH", log_file)
        from press.daemon import daemon_logs

        rc = daemon_logs(lines=None, level="info")
        assert rc == 0
        out = capsys.readouterr().out
        assert "DEBUG" not in out
        assert "INFO" in out

    def test_level_filter_error_shows_only_error(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        log_file = self._write_log(tmp_path, _SAMPLE_LINES)
        monkeypatch.setattr("press.daemon._LOG_PATH", log_file)
        from press.daemon import daemon_logs

        rc = daemon_logs(lines=None, level="error")
        assert rc == 0
        out = capsys.readouterr().out
        assert "INFO" not in out
        assert "DEBUG" not in out
        assert "WARNING" not in out
        assert "ERROR" in out

    def test_as_json_emits_ndjson(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        log_file = self._write_log(tmp_path, _SAMPLE_LINES[:1])
        monkeypatch.setattr("press.daemon._LOG_PATH", log_file)
        from press.daemon import daemon_logs

        rc = daemon_logs(lines=None, level="all", as_json=True)
        assert rc == 0
        raw = capsys.readouterr().out.strip()
        obj = json.loads(raw)
        assert obj["ts"] == "2026-06-01T10:00:00"
        assert obj["level"] == "INFO"
        assert obj["msg"] == "daemon started"

    def test_malformed_lines_are_skipped(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        lines = ["not a valid log line\n", *_SAMPLE_LINES[:1]]
        log_file = self._write_log(tmp_path, lines)
        monkeypatch.setattr("press.daemon._LOG_PATH", log_file)
        from press.daemon import daemon_logs

        rc = daemon_logs(lines=None, level="all")
        assert rc == 0
        out = capsys.readouterr().out
        assert "not a valid" not in out
        assert "daemon started" in out


# ---------------------------------------------------------------------------
# PARAMETRIC_COMMANDS registry completeness
# ---------------------------------------------------------------------------


class TestParametricCommandRegistry:
    def test_aliases_consistent_with_parametric_aliases(self) -> None:
        from press.commands import PARAMETRIC_ALIASES, PARAMETRIC_COMMANDS

        derived = {alias: cmd.name for cmd in PARAMETRIC_COMMANDS for alias in cmd.aliases}
        assert derived == PARAMETRIC_ALIASES

    def test_parametric_command_index_contains_all_names_and_aliases(self) -> None:
        from press.commands import PARAMETRIC_COMMAND_INDEX, PARAMETRIC_COMMANDS

        for cmd in PARAMETRIC_COMMANDS:
            assert cmd.name in PARAMETRIC_COMMAND_INDEX
            for alias in cmd.aliases:
                assert alias in PARAMETRIC_COMMAND_INDEX
                assert PARAMETRIC_COMMAND_INDEX[alias] is cmd

    def test_all_modules_are_importable(self) -> None:
        import importlib

        from press.commands import PARAMETRIC_COMMANDS

        for cmd in PARAMETRIC_COMMANDS:
            mod = importlib.import_module(cmd.module)
            assert hasattr(mod, cmd.fn), f"{cmd.module}.{cmd.fn} not found"

    def test_sql_in_daemon_kwargs_uses_config(self) -> None:
        from press.commands import PARAMETRIC_COMMAND_INDEX
        from press.config import PressConfig, SqlInConfig

        cmd = PARAMETRIC_COMMAND_INDEX["sql-in"]
        assert cmd.daemon_kwargs is not None
        cfg = PressConfig(sql_in=SqlInConfig(quote_char='"', wrap=True))
        kw = cmd.daemon_kwargs(cfg)
        assert kw == {"quote_char": '"', "wrap": True}

    def test_non_sql_commands_have_no_daemon_kwargs(self) -> None:
        from press.commands import PARAMETRIC_COMMAND_INDEX

        for name in ("trim", "dedupe", "sort", "json-format", "fix-encoding"):
            cmd = PARAMETRIC_COMMAND_INDEX[name]
            assert cmd.daemon_kwargs is None

    def test_transforms_init_exposes_parametric_fns(self) -> None:
        import press.transforms as _t
        from press.commands import PARAMETRIC_COMMANDS

        for cmd in PARAMETRIC_COMMANDS:
            assert cmd.fn in _t.__all__, f"{cmd.fn} missing from press.transforms.__all__"
            fn = getattr(_t, cmd.fn)
            assert callable(fn)


# ---------------------------------------------------------------------------
# Default hotkey bindings ↔ command registry consistency
# ---------------------------------------------------------------------------


class TestDefaultBindingsDispatchable:
    """Every default hotkey binding must resolve to a dispatchable command.

    Guards the last remaining sync point between ``config._DEFAULT_BINDINGS``
    and the command registries: a typo or a renamed command would otherwise
    only surface as a runtime notification error in the daemon.
    """

    def test_all_default_binding_values_are_dispatchable(self) -> None:
        from press.commands import (
            DAEMON_SPECIAL_COMMANDS,
            PARAMETRIC_COMMAND_INDEX,
            SIMPLE_COMMAND_INDEX,
        )
        from press.config import _DEFAULT_BINDINGS

        dispatchable = (
            SIMPLE_COMMAND_INDEX.keys() | PARAMETRIC_COMMAND_INDEX.keys() | DAEMON_SPECIAL_COMMANDS
        )
        for key, command in _DEFAULT_BINDINGS.items():
            assert command in dispatchable, (
                f"default binding {key!r} -> {command!r} is not a dispatchable command"
            )
