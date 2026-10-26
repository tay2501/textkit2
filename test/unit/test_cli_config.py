"""Tests for the ``press config`` command group (path / list / validate / reset)."""

from __future__ import annotations

import tomllib
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path


def _run(*argv: str) -> int:
    from press.__main__ import make_parser

    args = make_parser().parse_args(["config", *argv])
    result: int = args.func(args)
    return result


@pytest.fixture
def default_cfg(tmp_path: Path) -> Iterator[Path]:
    """Point the default config path at an (initially missing) temp file."""
    path = tmp_path / "config.toml"
    with patch("press.config.default_config_path", return_value=path):
        yield path


class TestConfigPath:
    def test_prints_the_default_path_even_when_missing(
        self, default_cfg: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        assert _run("path") == 0
        assert capsys.readouterr().out == f"{default_cfg}\n"

    def test_takes_no_file_option(self) -> None:
        with pytest.raises(SystemExit):
            _run("path", "--file", "x.toml")


class TestConfigList:
    def test_missing_default_file_lists_the_defaults(
        self, default_cfg: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from press.config import PressConfig

        assert _run("list") == 0
        listed = tomllib.loads(capsys.readouterr().out)
        assert listed["schema_version"] == PressConfig().schema_version
        assert "hotkeys" in listed

    def test_shows_values_from_the_file(
        self, default_cfg: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        default_cfg.write_text("[sql_in]\nwrap = true\n", encoding="utf-8")

        assert _run("list") == 0
        assert tomllib.loads(capsys.readouterr().out)["sql_in"]["wrap"] is True

    def test_ls_alias(self, default_cfg: Path, capsys: pytest.CaptureFixture[str]) -> None:
        assert _run("ls") == 0
        assert "schema_version" in capsys.readouterr().out

    def test_invalid_file_fails(
        self, default_cfg: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        default_cfg.write_text("not valid ][", encoding="utf-8")

        assert _run("list") == 1
        captured = capsys.readouterr()
        assert captured.out == ""
        assert "error" in captured.err

    def test_non_integer_schema_version_fails_cleanly(
        self, default_cfg: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        default_cfg.write_text("schema_version = [1]\n", encoding="utf-8")

        assert _run("list") == 1
        assert "schema_version" in capsys.readouterr().err

    def test_explicit_missing_file_fails(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        missing = tmp_path / "nope.toml"

        assert _run("list", "--file", str(missing)) == 1
        assert f"not found: {missing}" in capsys.readouterr().err


class TestConfigValidate:
    def test_missing_default_file_is_ok(
        self, default_cfg: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        assert _run("validate") == 0
        out = capsys.readouterr().out
        assert "defaults will be used" in out
        assert "WindowsPath" not in out
        assert "PosixPath" not in out

    def test_explicit_missing_file_fails(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        missing = tmp_path / "nope.toml"

        assert _run("validate", "--file", str(missing)) == 1
        assert f"not found: {missing}" in capsys.readouterr().err

    def test_valid_file_message_shows_a_plain_path(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        cfg = tmp_path / "c.toml"
        cfg.write_text("[sql_in]\nwrap = true\n", encoding="utf-8")

        assert _run("validate", "--file", str(cfg)) == 0
        assert f"{cfg}: valid" in capsys.readouterr().out


class TestConfigResetConfirmation:
    """Like `claude auto-mode reset` / `gh repo delete`: ask, or take --yes."""

    def _existing(self, tmp_path: Path) -> Path:
        cfg = tmp_path / "config.toml"
        cfg.write_text("[sql_in]\nwrap = true\n", encoding="utf-8")
        return cfg

    def _wrap(self, cfg: Path) -> bool:
        return bool(tomllib.loads(cfg.read_text(encoding="utf-8"))["sql_in"]["wrap"])

    def test_yes_skips_the_prompt(self, tmp_path: Path) -> None:
        cfg = self._existing(tmp_path)
        with patch("sys.stdin.isatty", return_value=False):
            assert _run("reset", "-y", "--file", str(cfg)) == 0
        assert self._wrap(cfg) is False

    def test_long_yes(self, tmp_path: Path) -> None:
        cfg = self._existing(tmp_path)
        assert _run("reset", "--yes", "--file", str(cfg)) == 0
        assert self._wrap(cfg) is False

    def test_tty_confirmed(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        cfg = self._existing(tmp_path)
        with (
            patch("sys.stdin.isatty", return_value=True),
            patch("builtins.input", return_value="y"),
        ):
            assert _run("reset", "--file", str(cfg)) == 0
        assert self._wrap(cfg) is False
        assert "[y/N]" in capsys.readouterr().err

    @pytest.mark.parametrize("answer", ["", "n", "no", "yes please"])
    def test_tty_declined_changes_nothing(self, tmp_path: Path, answer: str) -> None:
        cfg = self._existing(tmp_path)
        with (
            patch("sys.stdin.isatty", return_value=True),
            patch("builtins.input", return_value=answer),
        ):
            assert _run("reset", "--file", str(cfg)) == 1
        assert self._wrap(cfg) is True
        assert not cfg.with_suffix(".toml.bak").exists()

    @pytest.mark.parametrize("exc", [EOFError, KeyboardInterrupt])
    def test_tty_interrupted_changes_nothing(
        self, tmp_path: Path, exc: type[BaseException]
    ) -> None:
        cfg = self._existing(tmp_path)
        with (
            patch("sys.stdin.isatty", return_value=True),
            patch("builtins.input", side_effect=exc),
        ):
            assert _run("reset", "--file", str(cfg)) == 1
        assert self._wrap(cfg) is True

    def test_non_tty_without_yes_is_a_usage_error(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        cfg = self._existing(tmp_path)
        with patch("sys.stdin.isatty", return_value=False):
            assert _run("reset", "--file", str(cfg)) == 2
        assert "--yes" in capsys.readouterr().err
        assert self._wrap(cfg) is True

    def test_nothing_to_lose_needs_no_prompt(self, tmp_path: Path) -> None:
        cfg = tmp_path / "config.toml"
        with patch("sys.stdin.isatty", return_value=False):
            assert _run("reset", "--file", str(cfg)) == 0
        assert cfg.exists()

    def test_section_reset_of_an_invalid_file_fails(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        cfg = tmp_path / "config.toml"
        cfg.write_text("not valid ][", encoding="utf-8")

        assert _run("reset", "-y", "--section", "ui", "--file", str(cfg)) == 1
        assert cfg.read_text(encoding="utf-8") == "not valid ]["
        assert "without --section" in capsys.readouterr().err
