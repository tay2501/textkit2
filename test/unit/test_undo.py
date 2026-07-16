"""Tests for undo — restore the clipboard text press overwrote."""

from pathlib import Path
from unittest.mock import patch

import pytest

from press.transforms import undo as undo_mod
from press.transforms.undo import save_snapshot, swap_undo, undo_disabled

# ---------------------------------------------------------------------------
# File-based slot (CLI layer)
# ---------------------------------------------------------------------------


@pytest.fixture
def undo_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "undo.txt"
    monkeypatch.setattr(undo_mod, "undo_path", lambda: path)
    return path


class _FakeClipboard:
    def __init__(self, text: str = "") -> None:
        self.text = text

    def get(self) -> str:
        return self.text

    def set(self, text: str) -> None:
        self.text = text


class TestSwapUndo:
    def test_swap_restores_snapshot(self, undo_file: Path) -> None:
        save_snapshot("before")
        clip = _FakeClipboard("after")
        swap_undo(clip.get, clip.set)
        assert clip.text == "before"

    def test_swap_twice_is_redo(self, undo_file: Path) -> None:
        save_snapshot("before")
        clip = _FakeClipboard("after")
        swap_undo(clip.get, clip.set)
        swap_undo(clip.get, clip.set)
        assert clip.text == "after"

    def test_no_snapshot_raises_file_not_found(self, undo_file: Path) -> None:
        clip = _FakeClipboard("x")
        with pytest.raises(FileNotFoundError):
            swap_undo(clip.get, clip.set)
        assert clip.text == "x"  # clipboard untouched

    def test_unreadable_clipboard_becomes_empty_redo_slot(self, undo_file: Path) -> None:
        save_snapshot("before")

        def _failing_get() -> str:
            raise RuntimeError("clipboard is empty")

        clip = _FakeClipboard()
        swap_undo(_failing_get, clip.set)
        assert clip.text == "before"
        # The redo slot degraded to empty text
        swap_undo(clip.get, clip.set)
        assert clip.text == ""

    def test_japanese_roundtrip(self, undo_file: Path) -> None:
        save_snapshot("変換前のテキスト")
        clip = _FakeClipboard("ヘンカンゴ")
        swap_undo(clip.get, clip.set)
        assert clip.text == "変換前のテキスト"


class TestUndoDisabled:
    def test_default_enabled(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("PRESS_NO_UNDO", raising=False)
        assert undo_disabled() is False

    def test_zero_means_enabled(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("PRESS_NO_UNDO", "0")
        assert undo_disabled() is False

    def test_one_disables(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("PRESS_NO_UNDO", "1")
        assert undo_disabled() is True


# ---------------------------------------------------------------------------
# CLI snapshot hook (_cli_helpers._snapshot_clipboard_for_undo)
# ---------------------------------------------------------------------------


class TestSnapshotHook:
    def test_snapshot_written_before_overwrite(
        self, undo_file: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from press._cli_helpers import _snapshot_clipboard_for_undo

        monkeypatch.delenv("PRESS_NO_UNDO", raising=False)
        with (
            patch("press.clipboard.clipboard_has_sensitive_marks", return_value=False),
            patch("press.clipboard.get_clipboard_text", return_value="old text"),
        ):
            _snapshot_clipboard_for_undo()
        assert undo_file.exists()
        clip = _FakeClipboard("new")
        swap_undo(clip.get, clip.set)
        assert clip.text == "old text"

    def test_sensitive_content_not_snapshotted(
        self, undo_file: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from press._cli_helpers import _snapshot_clipboard_for_undo

        monkeypatch.delenv("PRESS_NO_UNDO", raising=False)
        with (
            patch("press.clipboard.clipboard_has_sensitive_marks", return_value=True),
            patch("press.clipboard.get_clipboard_text", return_value="s3cret"),
        ):
            _snapshot_clipboard_for_undo()
        assert not undo_file.exists()

    def test_opt_out_env_skips_snapshot(
        self, undo_file: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from press._cli_helpers import _snapshot_clipboard_for_undo

        monkeypatch.setenv("PRESS_NO_UNDO", "1")
        with (
            patch("press.clipboard.clipboard_has_sensitive_marks", return_value=False),
            patch("press.clipboard.get_clipboard_text", return_value="old"),
        ):
            _snapshot_clipboard_for_undo()
        assert not undo_file.exists()

    def test_clipboard_failure_does_not_raise(
        self, undo_file: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from press._cli_helpers import _snapshot_clipboard_for_undo

        monkeypatch.delenv("PRESS_NO_UNDO", raising=False)
        with patch(
            "press.clipboard.clipboard_has_sensitive_marks",
            side_effect=RuntimeError("boom"),
        ):
            _snapshot_clipboard_for_undo()  # must not propagate
        assert not undo_file.exists()


# ---------------------------------------------------------------------------
# CLI command (press undo)
# ---------------------------------------------------------------------------


class TestUndoCliCommand:
    def test_nothing_to_undo_exits_1(
        self, undo_file: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from press.__main__ import make_parser

        parser = make_parser()
        args = parser.parse_args(["undo"])
        assert args.func(args) == 1
        assert "nothing to undo" in capsys.readouterr().err

    def test_quiet_suppresses_message(
        self, undo_file: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from press.__main__ import make_parser

        parser = make_parser()
        args = parser.parse_args(["undo", "-q"])
        assert args.func(args) == 1
        assert capsys.readouterr().err == ""

    def test_undo_swaps_clipboard(self, undo_file: Path) -> None:
        from press.__main__ import make_parser

        save_snapshot("before")
        clip = _FakeClipboard("after")
        with (
            patch("press.clipboard.get_clipboard_text", side_effect=clip.get),
            patch("press.clipboard.set_clipboard_text", side_effect=clip.set),
        ):
            parser = make_parser()
            args = parser.parse_args(["undo"])
            assert args.func(args) == 0
        assert clip.text == "before"


# ---------------------------------------------------------------------------
# Daemon in-memory slot (CommandDispatcher)
# ---------------------------------------------------------------------------


class TestDispatcherUndo:
    def _dispatcher(self, *, notify_level: str = "off") -> object:
        from press.config import PressConfig, UiConfig
        from press.daemon import CommandDispatcher

        return CommandDispatcher(PressConfig(ui=UiConfig(notify_level=notify_level)))

    def test_transform_then_undo_restores(self) -> None:
        clip = _FakeClipboard("abc")
        with (
            patch("press.clipboard.get_clipboard_text", side_effect=clip.get),
            patch("press.clipboard.set_clipboard_text", side_effect=clip.set),
            patch("press.clipboard.clipboard_has_sensitive_marks", return_value=False),
        ):
            d = self._dispatcher()
            d.dispatch("upper")
            assert clip.text == "ABC"
            d.dispatch("undo")
            assert clip.text == "abc"
            d.dispatch("undo")  # redo
            assert clip.text == "ABC"

    def test_undo_without_history_notifies_error(self) -> None:
        from unittest.mock import MagicMock

        clip = _FakeClipboard("x")
        with (
            patch("press.clipboard.get_clipboard_text", side_effect=clip.get),
            patch("press.clipboard.set_clipboard_text", side_effect=clip.set),
        ):
            d = self._dispatcher(notify_level="error")
            icon = MagicMock()
            d.set_icon(icon)
            d.dispatch("undo")
            assert clip.text == "x"  # untouched
            icon.notify.assert_called_once()
            assert "nothing to undo" in icon.notify.call_args.args[0]

    def test_sensitive_clipboard_not_remembered(self) -> None:
        clip = _FakeClipboard("s3cret")
        with (
            patch("press.clipboard.get_clipboard_text", side_effect=clip.get),
            patch("press.clipboard.set_clipboard_text", side_effect=clip.set),
            patch("press.clipboard.clipboard_has_sensitive_marks", return_value=True),
        ):
            d = self._dispatcher()
            d.dispatch("upper")
            assert clip.text == "S3CRET"
            assert d._undo_text is None  # type: ignore[attr-defined]

    def test_clear_is_undoable(self) -> None:
        clip = _FakeClipboard("precious")
        with (
            patch("press.clipboard.get_clipboard_text", side_effect=clip.get),
            patch("press.clipboard.set_clipboard_text", side_effect=clip.set),
            patch("press.clipboard.clear_clipboard", side_effect=lambda: clip.set("")),
            patch("press.clipboard.clipboard_has_sensitive_marks", return_value=False),
        ):
            d = self._dispatcher()
            d.dispatch("clear")
            assert clip.text == ""
            d.dispatch("undo")
            assert clip.text == "precious"

    def test_opt_out_env_disables_daemon_undo(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("PRESS_NO_UNDO", "1")
        clip = _FakeClipboard("abc")
        with (
            patch("press.clipboard.get_clipboard_text", side_effect=clip.get),
            patch("press.clipboard.set_clipboard_text", side_effect=clip.set),
            patch("press.clipboard.clipboard_has_sensitive_marks", return_value=False),
        ):
            d = self._dispatcher()
            d.dispatch("upper")
            assert d._undo_text is None  # type: ignore[attr-defined]
