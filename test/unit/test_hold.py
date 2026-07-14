"""Unit tests for press.transforms.hold and daemon hold integration (Phase 4)."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# toggle_hold_file — file-based hold/release
# ---------------------------------------------------------------------------


class TestToggleHoldFileHold:
    """First call: no file exists → hold (save clipboard to file)."""

    def test_returns_true_when_holding(self, tmp_path: Path) -> None:
        from press.transforms.hold import toggle_hold_file

        hold_file = tmp_path / "hold.txt"
        get_text = MagicMock(return_value="hello world")
        set_text = MagicMock()

        result = toggle_hold_file(hold_file, get_text, set_text)

        assert result is True

    def test_file_is_created_with_clipboard_content(self, tmp_path: Path) -> None:
        from press.transforms.hold import toggle_hold_file

        hold_file = tmp_path / "hold.txt"
        get_text = MagicMock(return_value="hello world")
        set_text = MagicMock()

        toggle_hold_file(hold_file, get_text, set_text)

        assert hold_file.exists()
        raw = hold_file.read_bytes()
        if sys.platform == "win32":
            # DPAPI-encrypted: the clipboard text must not be readable in plaintext
            assert b"hello world" not in raw
            assert raw.startswith(b"press-dpapi\x00")
        else:
            assert raw.decode("utf-8") == "hello world"

    def test_set_text_not_called_on_hold(self, tmp_path: Path) -> None:
        from press.transforms.hold import toggle_hold_file

        hold_file = tmp_path / "hold.txt"
        get_text = MagicMock(return_value="hello world")
        set_text = MagicMock()

        toggle_hold_file(hold_file, get_text, set_text)

        set_text.assert_not_called()

    def test_creates_parent_dirs(self, tmp_path: Path) -> None:
        from press.transforms.hold import toggle_hold_file

        hold_file = tmp_path / "subdir" / "nested" / "hold.txt"
        get_text = MagicMock(return_value="abc")
        set_text = MagicMock()

        toggle_hold_file(hold_file, get_text, set_text)

        assert hold_file.exists()


class TestToggleHoldFileRelease:
    """Second call: file exists → release (restore clipboard, delete file)."""

    def test_returns_false_when_releasing(self, tmp_path: Path) -> None:
        from press.transforms.hold import toggle_hold_file

        hold_file = tmp_path / "hold.txt"
        hold_file.write_text("saved text", encoding="utf-8")
        get_text = MagicMock(return_value="current")
        set_text = MagicMock()

        result = toggle_hold_file(hold_file, get_text, set_text)

        assert result is False

    def test_set_text_called_with_saved_content(self, tmp_path: Path) -> None:
        from press.transforms.hold import toggle_hold_file

        hold_file = tmp_path / "hold.txt"
        hold_file.write_text("saved text", encoding="utf-8")
        get_text = MagicMock(return_value="current")
        set_text = MagicMock()

        toggle_hold_file(hold_file, get_text, set_text)

        set_text.assert_called_once_with("saved text")

    def test_file_is_deleted_after_release(self, tmp_path: Path) -> None:
        from press.transforms.hold import toggle_hold_file

        hold_file = tmp_path / "hold.txt"
        hold_file.write_text("saved text", encoding="utf-8")
        get_text = MagicMock(return_value="current")
        set_text = MagicMock()

        toggle_hold_file(hold_file, get_text, set_text)

        assert not hold_file.exists()


class TestToggleHoldFileRoundTrip:
    """Hold then release restores the original text end-to-end."""

    def test_round_trip_restores_original_text(self, tmp_path: Path) -> None:
        from press.transforms.hold import toggle_hold_file

        hold_file = tmp_path / "hold.txt"
        original = "original clipboard text"
        clipboard: list[str] = [original]

        def get_text() -> str:
            return clipboard[0]

        def set_text(text: str) -> None:
            clipboard[0] = text

        # Hold
        held = toggle_hold_file(hold_file, get_text, set_text)
        assert held is True

        # Simulate clipboard changing
        clipboard[0] = "something else"

        # Release
        released = toggle_hold_file(hold_file, get_text, set_text)
        assert released is False
        assert clipboard[0] == original


# ---------------------------------------------------------------------------
# DPAPI encryption of the hold file
# ---------------------------------------------------------------------------


class TestLegacyPlaintextHoldFile:
    """Pre-encryption hold files (plaintext) must still release correctly."""

    def test_plaintext_file_releases(self, tmp_path: Path) -> None:
        from press.transforms.hold import toggle_hold_file

        hold_file = tmp_path / "hold.txt"
        hold_file.write_text("legacy text\nsecond line", encoding="utf-8")
        set_text = MagicMock()

        released = toggle_hold_file(hold_file, MagicMock(), set_text)

        assert released is False
        set_text.assert_called_once_with("legacy text\nsecond line")
        assert not hold_file.exists()


@pytest.mark.windows_only
class TestDpapi:
    def test_roundtrip(self) -> None:
        from press._dpapi import protect, unprotect

        secret = "秘密 secret\r\nline2".encode()
        blob = protect(secret)
        assert blob != secret
        assert secret not in blob
        assert unprotect(blob) == secret

    def test_unprotect_garbage_raises(self) -> None:
        from press._dpapi import unprotect

        with pytest.raises(RuntimeError, match="CryptUnprotectData"):
            unprotect(b"not a dpapi blob")

    def test_hold_roundtrip_through_encryption(self, tmp_path: Path) -> None:
        """Hold then release restores the exact text via the encrypted file."""
        from press.transforms.hold import toggle_hold_file

        hold_file = tmp_path / "hold.txt"
        clipboard: list[str] = ["CRLF text\r\nwith 日本語"]

        def set_text(text: str) -> None:
            clipboard[0] = text

        toggle_hold_file(hold_file, lambda: clipboard[0], set_text)
        clipboard[0] = "overwritten"
        toggle_hold_file(hold_file, lambda: clipboard[0], set_text)

        assert clipboard[0] == "CRLF text\r\nwith 日本語"


# ---------------------------------------------------------------------------
# press clear --hold — discard the hold file
# ---------------------------------------------------------------------------


class TestClearHoldOption:
    def test_clear_hold_discards_hold_file(self, tmp_path: Path) -> None:
        from press.__main__ import make_parser

        hold_file = tmp_path / "hold.txt"
        hold_file.write_text("stale", encoding="utf-8")
        with (
            patch("press.clipboard.clear_clipboard"),
            patch("press.transforms.hold.hold_path", return_value=hold_file),
        ):
            args = make_parser().parse_args(["clear", "--hold"])
            assert args.func(args) == 0
        assert not hold_file.exists()

    def test_clear_without_hold_keeps_the_file(self, tmp_path: Path) -> None:
        from press.__main__ import make_parser

        hold_file = tmp_path / "hold.txt"
        hold_file.write_text("keep me", encoding="utf-8")
        with (
            patch("press.clipboard.clear_clipboard"),
            patch("press.transforms.hold.hold_path", return_value=hold_file),
        ):
            args = make_parser().parse_args(["clear"])
            assert args.func(args) == 0
        assert hold_file.exists()


# ---------------------------------------------------------------------------
# hold_path — default path helper
# ---------------------------------------------------------------------------


class TestHoldPath:
    def test_returns_path_instance(self) -> None:
        from press.transforms.hold import hold_path

        p = hold_path()
        assert isinstance(p, Path)

    def test_filename_is_hold_txt(self) -> None:
        from press.transforms.hold import hold_path

        assert hold_path().name == "hold.txt"

    def test_parent_dir_contains_press(self) -> None:
        from press.transforms.hold import hold_path

        assert "press" in hold_path().parts


# ---------------------------------------------------------------------------
# CommandDispatcher._toggle_hold — in-memory daemon hold
# ---------------------------------------------------------------------------


class TestCommandDispatcherToggleHoldInMemory:
    """_toggle_hold delegates to ClipboardGuard (None = not held, str = held)."""

    def _make_dispatcher_with_mock_guard(
        self,
    ) -> tuple[object, object]:
        """Return (dispatcher, mock_guard) with Guard methods patched."""
        from press.config import PressConfig
        from press.daemon import CommandDispatcher

        d = CommandDispatcher(PressConfig())
        mock_guard = MagicMock()
        mock_guard.is_active = False
        mock_guard.protected_text = None
        d._guard = mock_guard  # type: ignore[assignment]
        return d, mock_guard

    def test_hold_sets_held_text(self) -> None:
        """engage() is called with clipboard text; guard becomes active."""

        with patch("press.clipboard.get_clipboard_text", return_value="clipboard data"):
            d, mock_guard = self._make_dispatcher_with_mock_guard()

            # Simulate guard not active initially
            mock_guard.is_active = False
            d._toggle_hold()

            mock_guard.engage.assert_called_once_with("clipboard data")

    def test_hold_calls_update_icon_with_holding_true(self) -> None:

        with patch("press.clipboard.get_clipboard_text", return_value="clipboard data"):
            d, mock_guard = self._make_dispatcher_with_mock_guard()
            mock_guard.is_active = False
            d._update_icon = MagicMock()  # type: ignore[method-assign]
            d._toggle_hold()
            d._update_icon.assert_called_once_with(holding=True)

    def test_release_restores_clipboard(self) -> None:
        """release() is called when guard is active; clipboard is not touched by dispatcher."""

        d, mock_guard = self._make_dispatcher_with_mock_guard()
        # Simulate guard already active (hold state)
        mock_guard.is_active = True

        d._toggle_hold()  # release

        mock_guard.release.assert_called_once()

    def test_release_clears_held_text(self) -> None:
        """After release(), guard.is_active becomes False (simulated via mock)."""

        d, mock_guard = self._make_dispatcher_with_mock_guard()

        # First call: engage
        mock_guard.is_active = False
        with patch("press.clipboard.get_clipboard_text", return_value="held data"):
            d._toggle_hold()
        mock_guard.engage.assert_called_once_with("held data")

        # Second call: release — mock transitions to inactive
        mock_guard.is_active = True
        d._toggle_hold()
        mock_guard.release.assert_called_once()

    def test_release_calls_update_icon_with_holding_false(self) -> None:

        d, mock_guard = self._make_dispatcher_with_mock_guard()
        mock_guard.is_active = True  # guard is currently active
        d._update_icon = MagicMock()  # type: ignore[method-assign]
        d._toggle_hold()  # triggers release path
        d._update_icon.assert_called_once_with(holding=False)


class TestCommandDispatcherDispatchHold:
    """dispatch("hold") must call _toggle_hold, not raise NotImplementedError."""

    def test_dispatch_hold_does_not_raise(self) -> None:
        from press.config import PressConfig
        from press.daemon import CommandDispatcher

        with patch("press.clipboard.get_clipboard_text", return_value="text"):
            d = CommandDispatcher(PressConfig())
            mock_icon = MagicMock()
            d.set_icon(mock_icon)
            # Patch guard to avoid real Win32 calls
            mock_guard = MagicMock()
            mock_guard.is_active = False
            d._guard = mock_guard  # type: ignore[assignment]
            # Should not raise
            d.dispatch("hold")

    def test_dispatch_hold_hold_state_changes(self) -> None:
        """dispatch("hold") transitions guard from inactive to active."""
        from press.config import PressConfig
        from press.daemon import CommandDispatcher

        with patch("press.clipboard.get_clipboard_text", return_value="text"):
            d = CommandDispatcher(PressConfig())
            mock_guard = MagicMock()
            mock_guard.is_active = False
            d._guard = mock_guard  # type: ignore[assignment]
            d.dispatch("hold")
            mock_guard.engage.assert_called_once_with("text")


# ---------------------------------------------------------------------------
# _create_tray_image — holding parameter changes background color
# ---------------------------------------------------------------------------


class TestCreateTrayImageHoldingFlag:
    @pytest.fixture(autouse=True)
    def _skip_if_no_pil(self) -> None:
        pytest.importorskip("PIL")

    def test_default_background_is_dark(self) -> None:
        from press.daemon._tray import _create_tray_image

        img = _create_tray_image(holding=False)
        pixel = img.getpixel((0, 0))
        # Dark background: R channel low, not red
        assert pixel[0] < 100  # type: ignore[index]

    def test_holding_background_is_red(self) -> None:
        from press.daemon._tray import _create_tray_image

        img = _create_tray_image(holding=True)
        pixel = img.getpixel((0, 0))
        # Red background: R channel high
        assert pixel[0] > 100  # type: ignore[index]

    def test_holding_false_is_default(self) -> None:
        from press.daemon._tray import _create_tray_image

        img_default = _create_tray_image()
        img_not_holding = _create_tray_image(holding=False)
        assert img_default.getpixel((0, 0)) == img_not_holding.getpixel((0, 0))
