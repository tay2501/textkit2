"""The single-command parser behaves exactly like the full one, and stays cheap.

``press <transform>`` builds a parser that knows only that transform
(``press.__main__._transform_parser``).  These tests pin the two halves of that
bargain: nothing the user can observe differs from the full parser, and the
modules the shortcut exists to avoid really are not imported.
"""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from press.__main__ import (
    _build_parser,
    _HelpFormatter,
    _terminal_columns,
    _transform_parser,
)
from press.commands import PARAMETRIC_COMMANDS, SIMPLE_COMMANDS

_PRESS_ROOT = Path(__file__).parent.parent.parent
_ALL_NAMES = sorted(
    name for cmd in (*SIMPLE_COMMANDS, *PARAMETRIC_COMMANDS) for name in (cmd.name, *cmd.aliases)
)


def _subparsers(parser: argparse.ArgumentParser) -> dict[str, argparse.ArgumentParser]:
    (sub,) = (a for a in parser._actions if isinstance(a, argparse._SubParsersAction))
    return dict(sub.choices)


@pytest.fixture(scope="module")
def full_subparsers() -> dict[str, argparse.ArgumentParser]:
    return _subparsers(_build_parser()[0])


class TestSameAsFullParser:
    @pytest.mark.parametrize("name", _ALL_NAMES)
    def test_help_is_identical(
        self,
        name: str,
        full_subparsers: dict[str, argparse.ArgumentParser],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("COLUMNS", "80")
        parser = _transform_parser([name])
        assert parser is not None
        assert _subparsers(parser)[name].format_help() == full_subparsers[name].format_help()

    @pytest.mark.parametrize("name", _ALL_NAMES)
    def test_only_the_named_command_is_registered(self, name: str) -> None:
        parser = _transform_parser([name])
        assert parser is not None
        registered = _subparsers(parser)
        assert name in registered
        assert len({id(p) for p in registered.values()}) == 1

    def test_alias_reaches_the_handler_as_typed(self) -> None:
        parser = _transform_parser(["up", "abc"])
        assert parser is not None
        args = parser.parse_args(["up", "abc"])
        assert (args.command, args.input) == ("up", "abc")

    def test_parametric_options_parse_the_same(self) -> None:
        argv = ["sort", "--reverse", "-n", "x"]
        fast = _transform_parser(argv)
        assert fast is not None
        full = _build_parser()[0]
        strip = {"func"}  # a fresh closure per build
        assert {k: v for k, v in vars(fast.parse_args(argv)).items() if k not in strip} == {
            k: v for k, v in vars(full.parse_args(argv)).items() if k not in strip
        }

    def test_abbreviated_options_stay_rejected(self) -> None:
        parser = _transform_parser(["trim"])
        assert parser is not None
        with pytest.raises(SystemExit):
            parser.parse_args(["trim", "--trail"])


class TestFallsBackToFullParser:
    @pytest.mark.parametrize(
        "argv",
        [
            [],
            ["--help"],
            ["--version"],
            ["-q", "upper"],
            ["dict"],
            ["daemon", "status"],
            ["genpass"],
            ["chain", "upper"],
            ["uper"],  # unknown: the full parser prints the grouped listing
        ],
    )
    def test_not_a_transform(self, argv: list[str]) -> None:
        assert _transform_parser(argv) is None

    def test_shell_completion_needs_every_command(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("_ARGCOMPLETE", "1")
        assert _transform_parser(["upper"]) is None


class TestTerminalColumns:
    """``_terminal_columns`` is ``shutil.get_terminal_size().columns`` without the import."""

    @pytest.mark.parametrize("value", ["120", "40", "0", "-5", "abc", ""])
    def test_matches_shutil_for_columns_env(
        self, value: str, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("COLUMNS", value)
        assert _terminal_columns() == shutil.get_terminal_size().columns

    def test_matches_shutil_without_columns_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("COLUMNS", raising=False)
        assert _terminal_columns() == shutil.get_terminal_size().columns

    def test_no_stdout_falls_back_to_80(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("COLUMNS", raising=False)
        monkeypatch.setattr(sys, "__stdout__", None)
        assert _terminal_columns() == 80

    def test_formatter_width_is_the_one_argparse_computes(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("COLUMNS", "100")
        assert _HelpFormatter("press")._width == argparse.HelpFormatter("press")._width == 98

    def test_explicit_width_wins(self) -> None:
        assert _HelpFormatter("press", width=50)._width == 50


_PROBE = """\
import io, sys
sys.argv = ["press", *{argv!r}]
sys.stdin = io.StringIO("A b")
from press.__main__ import main
try:
    main()
except SystemExit:
    pass
loaded = [m for m in {modules!r} if m in sys.modules]
print("LOADED", loaded, file=sys.stderr)
"""

_AVOIDED = [
    "shutil",
    "press._cli_chain",
    "press._cli_config",
    "press._cli_daemon",
    "press._cli_dict",
    "press._cli_notify",
    "press._cli_stash",
    "press._cli_trace",
]


def _loaded_after(argv: list[str], tmp_path: Path) -> str:
    """Run ``press *argv`` in a fresh interpreter; return its ``LOADED`` line."""
    env = {**os.environ, "PRESS_NO_DAEMON": "1", "APPDATA": str(tmp_path), "COLUMNS": "80"}
    result = subprocess.run(
        [sys.executable, "-c", _PROBE.format(argv=argv, modules=_AVOIDED)],
        capture_output=True,
        encoding="utf-8",
        env=env,
        cwd=_PRESS_ROOT,
        check=True,
    )
    return next(line for line in result.stderr.splitlines() if line.startswith("LOADED"))


class TestImportsAvoided:
    @pytest.mark.parametrize("argv", [["upper"], ["up"], ["sort", "--reverse"]])
    def test_transform_run_skips_command_groups_and_shutil(
        self, argv: list[str], tmp_path: Path
    ) -> None:
        assert _loaded_after(argv, tmp_path) == "LOADED []"

    def test_transform_help_skips_shutil(self, tmp_path: Path) -> None:
        # --help is where a formatter is really used, not just built.
        assert _loaded_after(["upper", "--help"], tmp_path) == "LOADED []"
