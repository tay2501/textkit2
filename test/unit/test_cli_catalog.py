"""Tests for the grouped command listing (press/_cli_catalog.py)."""

import argparse
import os
import subprocess
import sys
from pathlib import Path

import pytest

from press.__main__ import _build_parser, make_parser
from press._cli_catalog import _wrap_entries, format_catalog, suggest
from press.commands import PARAMETRIC_COMMANDS, SIMPLE_COMMANDS, TRANSFORM_CATEGORIES

_PRESS_ROOT = Path(__file__).parent.parent.parent
_UTF8_ENV = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8", "COLUMNS": "80"}


def _registered_names(parser: argparse.ArgumentParser) -> set[str]:
    """Every name and alias argparse accepts as the top-level COMMAND."""
    (sub,) = (a for a in parser._actions if isinstance(a, argparse._SubParsersAction))
    return set(sub.choices)


class TestCommandCatalog:
    def test_every_transform_module_has_a_category(self) -> None:
        modules = {cmd.module for cmd in (*SIMPLE_COMMANDS, *PARAMETRIC_COMMANDS)}
        assert modules == set(TRANSFORM_CATEGORIES)

    def test_catalog_matches_what_argparse_accepts(self) -> None:
        parser, catalog = _build_parser()
        listed = [name for group in catalog.values() for cmd in group for name in cmd]
        assert len(listed) == len(set(listed))
        assert set(listed) == _registered_names(parser)

    def test_categories_and_commands_are_alphabetical(self) -> None:
        _, catalog = _build_parser()
        assert list(catalog) == sorted(catalog)
        for group in catalog.values():
            names = [cmd[0] for cmd in group]
            assert names == sorted(names)

    def test_help_lists_commands_in_catalog_order(self) -> None:
        parser, catalog = _build_parser()
        (sub,) = (a for a in parser._actions if isinstance(a, argparse._SubParsersAction))
        help_order = [action.dest for action in sub._choices_actions]
        assert help_order == [cmd[0] for group in catalog.values() for cmd in group]


class TestFormatCatalog:
    def test_aliases_follow_their_command(self) -> None:
        text = format_catalog({"Case": [["upper", "up"], ["lower"]]}, width=80)
        assert text == "  Case\n    lower, upper (up)"

    def test_never_breaks_inside_an_entry(self) -> None:
        entries = ["base64-decode (bd)", "html-unescape (hu)", "url-decode (urld)"]
        lines = _wrap_entries(entries, width=30)
        assert lines == [
            "    base64-decode (bd),",
            "    html-unescape (hu),",
            "    url-decode (urld)",
        ]

    def test_lines_fit_width(self) -> None:
        _, catalog = _build_parser()
        for line in format_catalog(catalog, width=60).splitlines():
            assert len(line) <= 60


class TestSuggest:
    @pytest.mark.parametrize(
        ("typed", "expected"),
        [("uper", "upper"), ("kta", "katakana"), ("tirm", "trim"), ("zzzz", None)],
    )
    def test_closest_full_name(self, typed: str, expected: str | None) -> None:
        _, catalog = _build_parser()
        assert suggest(typed, catalog) == expected


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "press", *args],
        capture_output=True,
        encoding="utf-8",
        env=_UTF8_ENV,
        cwd=_PRESS_ROOT,
        check=False,
    )


class TestUnknownCommandCli:
    def test_exit_2_with_suggestion_and_grouped_listing(self) -> None:
        result = _run("uper")
        assert result.returncode == 2
        assert result.stdout == ""
        assert result.stderr.startswith("usage: press")
        assert "unknown command 'uper', maybe you meant 'upper'?" in result.stderr
        assert "  Case & separators\n" in result.stderr
        assert "invalid choice" not in result.stderr

    def test_no_suggestion_when_nothing_is_close(self) -> None:
        result = _run("zzzz")
        assert result.returncode == 2
        assert "press: error: unknown command 'zzzz'\n" in result.stderr

    def test_options_still_reach_argparse(self) -> None:
        assert _run("--version").returncode == 0

    def test_known_command_does_not_load_the_catalog(self) -> None:
        code = (
            "import sys; sys.argv = ['press', 'lower']; "
            "import io; sys.stdin = io.StringIO('A')\n"
            "from press.__main__ import main\n"
            "try:\n    main()\nexcept SystemExit:\n    pass\n"
            "print('press._cli_catalog' in sys.modules, 'difflib' in sys.modules, file=sys.stderr)"
        )
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            encoding="utf-8",
            env=_UTF8_ENV,
            cwd=_PRESS_ROOT,
            check=False,
        )
        assert result.stderr.strip().splitlines()[-1] == "False False"


def test_make_parser_still_returns_parser() -> None:
    assert isinstance(make_parser(), argparse.ArgumentParser)
