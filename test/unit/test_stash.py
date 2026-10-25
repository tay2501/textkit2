"""Tests for press.transforms.stash and the ``press stash`` command group."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path


# ---------------------------------------------------------------------------
# press.transforms.stash — push / pop / drop / stashed
# ---------------------------------------------------------------------------


class TestPush:
    def test_saves_the_clipboard_text(self, tmp_path: Path) -> None:
        from press.transforms.stash import push, stashed

        path = tmp_path / "stash.txt"
        push(path, "hello world", sensitive=False)

        assert stashed(path) == ("hello world", False)

    def test_file_is_encrypted_on_windows(self, tmp_path: Path) -> None:
        from press.transforms.stash import push

        path = tmp_path / "stash.txt"
        push(path, "hello world", sensitive=False)

        raw = path.read_bytes()
        if sys.platform == "win32":
            assert b"hello world" not in raw
            assert raw.startswith(b"press-dpapi")
        else:
            assert raw.decode("utf-8") == "hello world"

    def test_creates_parent_dirs(self, tmp_path: Path) -> None:
        from press.transforms.stash import push

        path = tmp_path / "a" / "b" / "stash.txt"
        push(path, "abc", sensitive=False)

        assert path.exists()

    def test_refuses_to_overwrite_an_existing_stash(self, tmp_path: Path) -> None:
        """One slot: a second push must not silently replace the first."""
        from press.transforms.stash import push, stashed

        path = tmp_path / "stash.txt"
        push(path, "first", sensitive=False)

        with pytest.raises(FileExistsError):
            push(path, "second", sensitive=False)
        assert stashed(path) == ("first", False)


class TestPop:
    def test_restores_and_deletes(self, tmp_path: Path) -> None:
        from press.transforms.stash import pop, push

        path = tmp_path / "stash.txt"
        push(path, "saved text", sensitive=False)
        set_text = MagicMock()

        pop(path, set_text)

        set_text.assert_called_once_with("saved text", False)
        assert not path.exists()

    def test_nothing_stashed_raises(self, tmp_path: Path) -> None:
        from press.transforms.stash import pop

        set_text = MagicMock()
        with pytest.raises(FileNotFoundError):
            pop(tmp_path / "stash.txt", set_text)
        set_text.assert_not_called()

    def test_failed_restore_keeps_the_stash(self, tmp_path: Path) -> None:
        """Restore first, delete second: a clipboard failure loses nothing."""
        from press.transforms.stash import pop, push

        path = tmp_path / "stash.txt"
        push(path, "keep me", sensitive=False)

        with pytest.raises(RuntimeError):
            pop(path, MagicMock(side_effect=RuntimeError("clipboard busy")))
        assert path.exists()

    def test_legacy_plaintext_file_pops(self, tmp_path: Path) -> None:
        from press.transforms.stash import pop

        path = tmp_path / "stash.txt"
        path.write_text("legacy text\nsecond line", encoding="utf-8")
        set_text = MagicMock()

        pop(path, set_text)

        set_text.assert_called_once_with("legacy text\nsecond line", False)

    def test_undecodable_file_raises_runtime_error(self, tmp_path: Path) -> None:
        """A corrupt file reaches the handler as RuntimeError, not a traceback."""
        from press.transforms.stash import pop

        path = tmp_path / "stash.txt"
        path.write_bytes(bytes([0xFF, 0xFE]) + b" not utf-8")

        with pytest.raises(RuntimeError, match="not valid UTF-8"):
            pop(path, MagicMock())


@pytest.mark.windows_only
class TestSensitiveRoundTrip:
    """A stashed secret comes back with its Win+V / Cloud Clipboard exclusion."""

    def test_sensitive_flag_survives(self, tmp_path: Path) -> None:
        from press.transforms.stash import pop, push

        path = tmp_path / "stash.txt"
        push(path, "p@ssw0rd", sensitive=True)
        set_text = MagicMock()

        pop(path, set_text)

        set_text.assert_called_once_with("p@ssw0rd", True)

    def test_exact_text_survives_encryption(self, tmp_path: Path) -> None:
        from press.transforms.stash import push, stashed

        path = tmp_path / "stash.txt"
        push(path, "CRLF text\r\nwith 日本語", sensitive=False)

        assert stashed(path) == ("CRLF text\r\nwith 日本語", False)


class TestDrop:
    def test_deletes_without_restoring(self, tmp_path: Path) -> None:
        from press.transforms.stash import drop, push

        path = tmp_path / "stash.txt"
        push(path, "x", sensitive=False)

        drop(path)

        assert not path.exists()

    def test_nothing_stashed_raises(self, tmp_path: Path) -> None:
        from press.transforms.stash import drop

        with pytest.raises(FileNotFoundError):
            drop(tmp_path / "stash.txt")


class TestStashPath:
    def test_lives_in_the_press_dir(self) -> None:
        from press._paths import press_dir
        from press.transforms.stash import stash_path

        assert stash_path() == press_dir() / "stash.txt"


# ---------------------------------------------------------------------------
# press stash — CLI
# ---------------------------------------------------------------------------


class _Clipboard:
    def __init__(self, text: str, *, sensitive: bool = False) -> None:
        self.text = text
        self.sensitive = sensitive

    def get(self) -> str:
        return self.text

    def set(self, text: str, *, sensitive: bool = False) -> None:
        self.text = text
        self.sensitive = sensitive


@pytest.fixture
def clipboard(tmp_path: Path) -> Iterator[_Clipboard]:
    clip = _Clipboard("current")
    with (
        patch("press.transforms.stash.stash_path", return_value=tmp_path / "stash.txt"),
        patch("press.clipboard.get_clipboard_text", side_effect=clip.get),
        patch("press.clipboard.set_clipboard_text", side_effect=clip.set),
        patch("press.clipboard.clipboard_has_sensitive_marks", side_effect=lambda: clip.sensitive),
        patch("press._cli_helpers._snapshot_clipboard_for_undo") as snapshot,
    ):
        clip.snapshot = snapshot  # type: ignore[attr-defined]
        yield clip


def _run(*argv: str) -> int:
    from press.__main__ import make_parser

    args = make_parser().parse_args(["stash", *argv])
    result: int = args.func(args)
    return result


class TestStashCli:
    def test_no_action_prints_help(self, capsys: pytest.CaptureFixture[str]) -> None:
        assert _run() == 0
        assert "push" in capsys.readouterr().out

    def test_push_then_pop_restores(
        self, clipboard: _Clipboard, capsys: pytest.CaptureFixture[str]
    ) -> None:
        assert _run("push") == 0
        clipboard.text = "overwritten"
        assert _run("pop") == 0

        assert clipboard.text == "current"
        err = capsys.readouterr().err
        assert "saved" in err
        assert "restored" in err

    def test_pop_snapshots_for_undo_before_restoring(self, clipboard: _Clipboard) -> None:
        _run("push")
        clipboard.snapshot.assert_not_called()  # type: ignore[attr-defined]
        _run("pop")
        clipboard.snapshot.assert_called_once()  # type: ignore[attr-defined]

    def test_push_keeps_the_sensitive_mark(self, clipboard: _Clipboard) -> None:
        clipboard.sensitive = True
        _run("push")
        clipboard.text, clipboard.sensitive = "other", False
        _run("pop")

        if sys.platform == "win32":
            assert clipboard.sensitive is True

    def test_second_push_fails_and_keeps_the_first(
        self, clipboard: _Clipboard, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _run("push")
        clipboard.text = "second"

        assert _run("push") == 1
        assert "pop" in capsys.readouterr().err  # hint: pop or drop first
        _run("pop")
        assert clipboard.text == "current"

    def test_pop_with_nothing_stashed_fails(
        self, clipboard: _Clipboard, capsys: pytest.CaptureFixture[str]
    ) -> None:
        assert _run("pop") == 1
        assert "no stash" in capsys.readouterr().err
        assert clipboard.text == "current"

    def test_drop_discards_without_restoring(self, clipboard: _Clipboard) -> None:
        _run("push")
        clipboard.text = "new"

        assert _run("drop") == 0
        assert clipboard.text == "new"
        assert _run("pop") == 1

    def test_drop_with_nothing_stashed_fails(self, clipboard: _Clipboard) -> None:
        assert _run("drop") == 1

    def test_list_empty_prints_nothing(
        self, clipboard: _Clipboard, capsys: pytest.CaptureFixture[str]
    ) -> None:
        assert _run("list") == 0
        assert capsys.readouterr().out == ""

    def test_list_reports_the_length_not_the_text(
        self, clipboard: _Clipboard, capsys: pytest.CaptureFixture[str]
    ) -> None:
        clipboard.text = "secret text"
        _run("push")

        assert _run("list") == 0
        out = capsys.readouterr().out
        assert "11 characters" in out
        assert "secret" not in out

    def test_quiet_silences_stderr(
        self, clipboard: _Clipboard, capsys: pytest.CaptureFixture[str]
    ) -> None:
        assert _run("push", "-q") == 0
        assert _run("pop", "-q") == 0
        assert _run("pop", "-q") == 1
        assert capsys.readouterr().err == ""

    def test_hold_is_not_a_cli_command(self) -> None:
        """``hold`` names the daemon's ClipboardGuard only."""
        from press.__main__ import make_parser

        with pytest.raises(SystemExit):
            make_parser().parse_args(["hold"])

    def test_clear_has_no_hold_option(self) -> None:
        from press.__main__ import make_parser

        with pytest.raises(SystemExit):
            make_parser().parse_args(["clear", "--hold"])
