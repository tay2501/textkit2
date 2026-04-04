"""Unit tests for press.transforms.hold and daemon hold integration (Phase 4)."""

from __future__ import annotations

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
        assert hold_file.read_text(encoding="utf-8") == "hello world"

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
    """_toggle_hold uses _held_text (None = not held, str = held)."""

    def test_hold_sets_held_text(self) -> None:
        from press.config import PressConfig
        from press.daemon import CommandDispatcher

        with patch("press.clipboard.get_clipboard_text", return_value="clipboard data"):
            d = CommandDispatcher(PressConfig())
            assert d._held_text is None
            d._toggle_hold()
            assert d._held_text == "clipboard data"

    def test_hold_calls_update_icon_with_holding_true(self) -> None:
        from press.config import PressConfig
        from press.daemon import CommandDispatcher

        with patch("press.clipboard.get_clipboard_text", return_value="clipboard data"):
            d = CommandDispatcher(PressConfig())
            d._update_icon = MagicMock()  # type: ignore[method-assign]
            d._toggle_hold()
            d._update_icon.assert_called_once_with(holding=True)

    def test_release_restores_clipboard(self) -> None:
        from press.config import PressConfig
        from press.daemon import CommandDispatcher

        with (
            patch("press.clipboard.get_clipboard_text", return_value="held data"),
            patch("press.clipboard.set_clipboard_text") as mock_set,
        ):
            d = CommandDispatcher(PressConfig())
            d._toggle_hold()  # hold
            mock_set.reset_mock()
            d._toggle_hold()  # release
            mock_set.assert_called_once_with("held data")

    def test_release_clears_held_text(self) -> None:
        from press.config import PressConfig
        from press.daemon import CommandDispatcher

        with (
            patch("press.clipboard.get_clipboard_text", return_value="held data"),
            patch("press.clipboard.set_clipboard_text"),
        ):
            d = CommandDispatcher(PressConfig())
            d._toggle_hold()  # hold
            assert d._held_text == "held data"
            d._toggle_hold()  # release
            assert d._held_text is None

    def test_release_calls_update_icon_with_holding_false(self) -> None:
        from press.config import PressConfig
        from press.daemon import CommandDispatcher

        with (
            patch("press.clipboard.get_clipboard_text", return_value="held data"),
            patch("press.clipboard.set_clipboard_text"),
        ):
            d = CommandDispatcher(PressConfig())
            d._toggle_hold()  # hold
            d._update_icon = MagicMock()  # type: ignore[method-assign]
            d._toggle_hold()  # release
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
            # Should not raise
            d.dispatch("hold")

    def test_dispatch_hold_hold_state_changes(self) -> None:
        from press.config import PressConfig
        from press.daemon import CommandDispatcher

        with patch("press.clipboard.get_clipboard_text", return_value="text"):
            d = CommandDispatcher(PressConfig())
            assert d._held_text is None
            d.dispatch("hold")
            assert d._held_text == "text"


# ---------------------------------------------------------------------------
# _create_tray_image — holding parameter changes background color
# ---------------------------------------------------------------------------


class TestCreateTrayImageHoldingFlag:
    @pytest.fixture(autouse=True)
    def _skip_if_no_pil(self) -> None:
        pytest.importorskip("PIL")

    def test_default_background_is_dark(self) -> None:
        from press.daemon import _create_tray_image

        img = _create_tray_image(holding=False)
        pixel = img.getpixel((0, 0))
        # Dark background: R channel low, not red
        assert pixel[0] < 100  # type: ignore[index]

    def test_holding_background_is_red(self) -> None:
        from press.daemon import _create_tray_image

        img = _create_tray_image(holding=True)
        pixel = img.getpixel((0, 0))
        # Red background: R channel high
        assert pixel[0] > 100  # type: ignore[index]

    def test_holding_false_is_default(self) -> None:
        from press.daemon import _create_tray_image

        img_default = _create_tray_image()
        img_not_holding = _create_tray_image(holding=False)
        assert img_default.getpixel((0, 0)) == img_not_holding.getpixel((0, 0))
