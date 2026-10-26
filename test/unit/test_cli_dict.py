"""Tests for the ``press dict`` command group (CLI dispatch and exit codes)."""

from __future__ import annotations

import io
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path


def _run(*argv: str) -> int:
    from press.__main__ import make_parser

    args = make_parser().parse_args(["dict", *argv])
    result: int = args.func(args)
    return result


@pytest.fixture
def configured(tmp_path: Path) -> Iterator[Path]:
    """Point ``[dictionary] files`` (the daemon's source) at a missing temp file."""
    from press.config import DictionaryConfig, PressConfig

    path = tmp_path / "configured.tsv"
    config = PressConfig(dictionary=DictionaryConfig(files=(str(path),)))
    with patch("press.config.load_config", return_value=config):
        yield path


class TestDictList:
    def test_missing_default_file_is_an_empty_list(
        self, configured: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        assert _run("list") == 0
        assert capsys.readouterr() == ("", "")

    def test_lists_the_configured_file(
        self, configured: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """CLI and daemon read the same dictionary ([dictionary] files[0])."""
        configured.write_text("k\tv\n", encoding="utf-8")

        assert _run("list") == 0
        assert capsys.readouterr().out == "k\tv\n"

    def test_ls_alias_lists_instead_of_transforming(
        self, configured: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        configured.write_text("k\tv\n", encoding="utf-8")

        assert _run("ls") == 0
        assert capsys.readouterr().out == "k\tv\n"

    def test_explicit_missing_file_fails(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        missing = tmp_path / "nope.tsv"

        assert _run("list", "--file", str(missing)) == 1
        assert f"not found: {missing}" in capsys.readouterr().err

    def test_group_level_file_reaches_the_action(
        self, configured: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """``press dict --file X list`` must read X, not the default."""
        other = tmp_path / "other.tsv"
        other.write_text("a\tb\n", encoding="utf-8")

        assert _run("--file", str(other), "list") == 0
        assert capsys.readouterr().out == "a\tb\n"


class TestDictAddRemove:
    def test_add_writes_the_configured_file(self, configured: Path) -> None:
        assert _run("add", "k", "v") == 0
        assert "k\tv" in configured.read_text(encoding="utf-8")

    def test_rm_alias_removes(self, configured: Path) -> None:
        configured.write_text("k\tv\n", encoding="utf-8")

        assert _run("rm", "k") == 0
        assert "k\tv" not in configured.read_text(encoding="utf-8")

    def test_remove_unknown_key_fails(
        self, configured: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        configured.write_text("k\tv\n", encoding="utf-8")

        assert _run("remove", "zz") == 1
        assert "key not found" in capsys.readouterr().err

    def test_remove_from_missing_file_fails_with_1(
        self, configured: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        assert _run("remove", "k") == 1
        assert "key not found" in capsys.readouterr().err


class TestDictTransform:
    def test_missing_dictionary_is_a_runtime_error(
        self, configured: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        with patch("sys.stdin", io.StringIO("k")):
            assert _run() == 1
        assert f"not found: {configured}" in capsys.readouterr().err

    def test_forward_lookup(self, configured: Path, capsys: pytest.CaptureFixture[str]) -> None:
        configured.write_text("k\tv\n", encoding="utf-8")

        with patch("sys.stdin", io.StringIO("k")):
            assert _run() == 0
        assert capsys.readouterr().out == "v"

    def test_invalid_config_fails_cleanly(self, capsys: pytest.CaptureFixture[str]) -> None:
        with patch("press.config.load_config", side_effect=ValueError("Invalid TOML in x")):
            assert _run("list") == 1
        assert "Invalid TOML" in capsys.readouterr().err

    def test_explicit_file_skips_the_config(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        tsv = tmp_path / "d.tsv"
        tsv.write_text("k\tv\n", encoding="utf-8")

        with patch("press.config.load_config", side_effect=AssertionError("not needed")):
            assert _run("list", "--file", str(tsv)) == 0
        assert capsys.readouterr().out == "k\tv\n"


class TestConfiguredDictPath:
    def test_daemon_and_cli_share_the_resolver(self, tmp_path: Path) -> None:
        from press.config import DictionaryConfig
        from press.dictionary import configured_dict_path, default_dict_path

        assert configured_dict_path(DictionaryConfig(files=(str(tmp_path / "a.tsv"),))) == (
            tmp_path / "a.tsv"
        )
        assert configured_dict_path(DictionaryConfig(files=())) == default_dict_path()
