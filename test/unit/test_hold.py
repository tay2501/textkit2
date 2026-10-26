"""Unit tests for the daemon's in-memory hold (ClipboardGuard) and DPAPI."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


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
