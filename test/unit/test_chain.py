"""Tests for ``press chain`` — multi-step transforms and named pipelines."""

from __future__ import annotations

import io
import os
import subprocess
import sys
from unittest.mock import patch

import pytest

from press.config import PressConfig, pipeline_errors

_ENV = {**os.environ, "PYTHONUTF8": "1", "PRESS_NO_DAEMON": "1"}


def _run(*args: str, stdin: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "press", "chain", *args],
        capture_output=True,
        text=True,
        encoding="utf-8",  # press reconfigures its streams to UTF-8
        input=stdin,
        env=_ENV,
    )


class TestChainCLI:
    def test_two_steps_apply_left_to_right(self) -> None:
        result = _run("trim", "upper", stdin="  hello \n")
        assert result.returncode == 0
        assert result.stdout == "  HELLO\n"

    def test_aliases_resolve(self) -> None:
        # tm = trim (parametric, default kwargs), lo = lower (simple)
        result = _run("tm", "lo", stdin="ABC  \n")
        assert result.returncode == 0
        assert result.stdout == "abc\n"

    def test_single_step_matches_direct_command(self) -> None:
        direct = subprocess.run(
            [sys.executable, "-m", "press", "upper"],
            capture_output=True,
            text=True,
            input="abc",
            env=_ENV,
        )
        chained = _run("upper", stdin="abc")
        assert chained.stdout == direct.stdout

    def test_order_matters(self) -> None:
        # snake→upper produces SNAKE_CASE; upper→snake keeps snake_case
        first = _run("snake", "upper", stdin="Hello World")
        second = _run("upper", "snake", stdin="Hello World")
        assert first.returncode == second.returncode == 0
        assert first.stdout != second.stdout

    def test_unknown_step_exits_one_with_message(self) -> None:
        result = _run("trim", "no-such-step", stdin="x")
        assert result.returncode == 1
        assert "unknown step" in result.stderr
        assert "no-such-step" in result.stderr
        assert result.stdout == ""  # atomic: nothing written on failure

    def test_no_steps_exits_two(self) -> None:
        result = _run(stdin="x")
        assert result.returncode == 2
        assert "no steps given" in result.stderr

    def test_failing_step_writes_nothing(self) -> None:
        # base64-decode on non-base64 input fails mid-chain
        result = _run("base64-decode", "upper", stdin="!!not base64!!")
        assert result.returncode == 1
        assert result.stdout == ""

    def test_ch_alias_works(self) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "press", "ch", "upper"],
            capture_output=True,
            text=True,
            input="abc",
            env=_ENV,
        )
        assert result.returncode == 0
        assert result.stdout == "ABC"


class TestChainPipelines:
    """[pipelines] expansion via a patched config (no file I/O)."""

    def _invoke(self, argv: list[str], stdin_text: str, pipelines: dict[str, tuple[str, ...]]):
        from press.__main__ import make_parser

        config = PressConfig(pipelines=pipelines)
        args = make_parser().parse_args(argv)
        with (
            patch("press.config.load_config", return_value=config),
            patch.object(sys, "stdin", io.StringIO(stdin_text)),
        ):
            return args.func(args)

    def test_pipeline_name_expands(self, capsys: pytest.CaptureFixture[str]) -> None:
        rc = self._invoke(
            ["chain", "cleanup"],
            "  A-B  \n",
            {"cleanup": ("trim", "lower", "underscore")},
        )
        assert rc == 0
        assert capsys.readouterr().out == "  a_b\n"

    def test_pipeline_mixed_with_commands(self, capsys: pytest.CaptureFixture[str]) -> None:
        rc = self._invoke(["chain", "cleanup", "upper"], "x-y", {"cleanup": ("underscore",)})
        assert rc == 0
        assert capsys.readouterr().out == "X_Y"

    def test_nested_pipeline_rejected(self, capsys: pytest.CaptureFixture[str]) -> None:
        rc = self._invoke(
            ["chain", "outer"],
            "x",
            {"outer": ("inner",), "inner": ("upper",)},
        )
        assert rc == 1
        assert "nesting is not supported" in capsys.readouterr().err

    def test_command_wins_name_collision(self, capsys: pytest.CaptureFixture[str]) -> None:
        # A pipeline named "upper" must not shadow the registry command
        rc = self._invoke(["chain", "upper"], "abc", {"upper": ("lower",)})
        assert rc == 0
        assert capsys.readouterr().out == "ABC"

    def test_list_shows_pipelines(self, capsys: pytest.CaptureFixture[str]) -> None:
        rc = self._invoke(["chain", "--list"], "", {"cleanup": ("trim", "lf")})
        assert rc == 0
        out = capsys.readouterr().out
        assert "cleanup" in out
        assert "trim -> lf" in out

    def test_list_empty_reports_hint(self, capsys: pytest.CaptureFixture[str]) -> None:
        rc = self._invoke(["chain", "--list"], "", {})
        assert rc == 0
        assert "[pipelines]" in capsys.readouterr().out


class TestPipelineErrors:
    """config.pipeline_errors — used by `press config validate`."""

    def test_valid_pipeline_no_errors(self) -> None:
        config = PressConfig(pipelines={"cleanup": ("trim", "dedupe", "lf")})
        assert pipeline_errors(config) == []

    def test_unknown_step_reported(self) -> None:
        config = PressConfig(pipelines={"bad": ("trim", "nope")})
        errors = pipeline_errors(config)
        assert len(errors) == 1
        assert "unknown step 'nope'" in errors[0]

    def test_name_shadowing_command_reported(self) -> None:
        config = PressConfig(pipelines={"upper": ("lower",)})
        errors = pipeline_errors(config)
        assert any("shadows a command name" in e for e in errors)

    def test_empty_pipeline_reported(self) -> None:
        config = PressConfig(pipelines={"empty": ()})
        errors = pipeline_errors(config)
        assert any("has no steps" in e for e in errors)

    def test_nested_pipeline_reported(self) -> None:
        config = PressConfig(pipelines={"outer": ("inner",), "inner": ("upper",)})
        errors = pipeline_errors(config)
        assert any("nesting is not supported" in e for e in errors)

    def test_alias_step_is_valid(self) -> None:
        config = PressConfig(pipelines={"cleanup": ("tm", "lo")})
        assert pipeline_errors(config) == []


class TestDispatcherPipelines:
    """Daemon hotkey dispatch resolves [pipelines] names."""

    def test_pipeline_runs_via_transform(self) -> None:
        from press.daemon import CommandDispatcher

        config = PressConfig(pipelines={"cleanup": ("trim", "lower")})
        d = CommandDispatcher(config)
        assert d.transform("cleanup", "  ABC  ") == "  abc"

    def test_pipeline_step_uses_daemon_config_kwargs(self) -> None:
        from press.config import TrimConfig
        from press.daemon import CommandDispatcher

        # trim with both=True from config must apply inside a pipeline too
        config = PressConfig(
            trim=TrimConfig(both=True),
            pipelines={"cleanup": ("trim",)},
        )
        d = CommandDispatcher(config)
        assert d.transform("cleanup", "  x  ") == "x"

    def test_unknown_command_still_raises(self) -> None:
        from press.daemon import CommandDispatcher

        d = CommandDispatcher(PressConfig())
        with pytest.raises(ValueError, match="unknown command"):
            d.transform("nope", "x")

    def test_non_registry_step_rejected(self) -> None:
        from press.daemon import CommandDispatcher

        config = PressConfig(pipelines={"bad": ("dict",)})
        d = CommandDispatcher(config)
        with pytest.raises(ValueError, match="not a transform command"):
            d.transform("bad", "x")

    def test_nested_pipeline_step_rejected(self) -> None:
        from press.daemon import CommandDispatcher

        config = PressConfig(pipelines={"outer": ("inner",), "inner": ("upper",)})
        d = CommandDispatcher(config)
        with pytest.raises(ValueError, match="not a transform command"):
            d.transform("outer", "x")
