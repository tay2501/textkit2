"""Tests for ClipboardGuard — dual-layer clipboard protection."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helper: build a fake pynput key object
# ---------------------------------------------------------------------------


def _make_keycode(char: str) -> MagicMock:
    """Return a MagicMock that behaves like pynput.keyboard.KeyCode."""
    key = MagicMock()
    key.char = char
    # Make it NOT equal to pynput special Key enum values
    key.__eq__ = lambda self, other: False  # type: ignore[misc]
    return key


def _make_special_key(name: str) -> MagicMock:
    """Return a MagicMock that behaves like pynput.keyboard.Key enum member."""
    key = MagicMock()
    key.char = None  # Key enum members have no .char
    key.name = name
    return key


# ---------------------------------------------------------------------------
# ClipboardGuard — state tests (platform-independent via mocking)
# ---------------------------------------------------------------------------


@pytest.mark.windows_only
class TestClipboardGuardInitialState:
    """ClipboardGuard starts inactive with no protected text."""

    def test_is_active_false_initially(self) -> None:
        from press.clipboard import ClipboardGuard

        with (
            patch("press.clipboard._win_set_text"),
            patch("press.clipboard._user32"),
            patch("press.clipboard._kernel32"),
        ):
            guard = ClipboardGuard()
            assert guard.is_active is False

    def test_protected_text_none_initially(self) -> None:
        from press.clipboard import ClipboardGuard

        with (
            patch("press.clipboard._win_set_text"),
            patch("press.clipboard._user32"),
            patch("press.clipboard._kernel32"),
        ):
            guard = ClipboardGuard()
            assert guard.protected_text is None


@pytest.mark.windows_only
class TestClipboardGuardEngage:
    """engage() activates protection and stores the protected text."""

    def test_is_active_true_after_engage(self) -> None:
        from press.clipboard import ClipboardGuard

        guard = ClipboardGuard()
        # Prevent actual Win32 thread/window creation
        with patch.object(guard, "_start_layer1"), patch.object(guard, "_start_layer2"):
            guard.engage("hello")
            assert guard.is_active is True

    def test_protected_text_set_after_engage(self) -> None:
        from press.clipboard import ClipboardGuard

        guard = ClipboardGuard()
        with patch.object(guard, "_start_layer1"), patch.object(guard, "_start_layer2"):
            guard.engage("保護テキスト")
            assert guard.protected_text == "保護テキスト"

    def test_engage_calls_both_layers(self) -> None:
        from press.clipboard import ClipboardGuard

        guard = ClipboardGuard()
        with (
            patch.object(guard, "_start_layer1") as mock_l1,
            patch.object(guard, "_start_layer2") as mock_l2,
        ):
            guard.engage("abc")
            mock_l1.assert_called_once()
            mock_l2.assert_called_once()


@pytest.mark.windows_only
class TestClipboardGuardRelease:
    """release() deactivates protection and clears protected text."""

    def test_is_active_false_after_release(self) -> None:
        from press.clipboard import ClipboardGuard

        guard = ClipboardGuard()
        with patch.object(guard, "_start_layer1"), patch.object(guard, "_start_layer2"):
            guard.engage("hello")

        with patch.object(guard, "_stop_layer1"), patch.object(guard, "_stop_layer2"):
            guard.release()
            assert guard.is_active is False

    def test_protected_text_none_after_release(self) -> None:
        from press.clipboard import ClipboardGuard

        guard = ClipboardGuard()
        with patch.object(guard, "_start_layer1"), patch.object(guard, "_start_layer2"):
            guard.engage("hello")

        with patch.object(guard, "_stop_layer1"), patch.object(guard, "_stop_layer2"):
            guard.release()
            assert guard.protected_text is None

    def test_release_calls_both_stop_methods(self) -> None:
        from press.clipboard import ClipboardGuard

        guard = ClipboardGuard()
        with patch.object(guard, "_start_layer1"), patch.object(guard, "_start_layer2"):
            guard.engage("hello")

        with (
            patch.object(guard, "_stop_layer1") as mock_l1,
            patch.object(guard, "_stop_layer2") as mock_l2,
        ):
            guard.release()
            mock_l1.assert_called_once()
            mock_l2.assert_called_once()

    def test_release_when_not_active_is_noop(self) -> None:
        """Calling release() without engage() must not raise."""
        from press.clipboard import ClipboardGuard

        guard = ClipboardGuard()
        # Should complete without error
        guard.release()
        assert guard.is_active is False


@pytest.mark.windows_only
class TestClipboardGuardDoubleEngage:
    """Calling engage() twice updates the protected text (idempotent re-arm)."""

    def test_double_engage_updates_text(self) -> None:
        from press.clipboard import ClipboardGuard

        guard = ClipboardGuard()
        with (
            patch.object(guard, "_start_layer1"),
            patch.object(guard, "_start_layer2"),
            patch.object(guard, "_stop_layer1"),
            patch.object(guard, "_stop_layer2"),
        ):
            guard.engage("first")
            guard.engage("second")
            assert guard.protected_text == "second"
            assert guard.is_active is True


# ---------------------------------------------------------------------------
# _PasteInterceptor — _is_paste_shortcut logic
# ---------------------------------------------------------------------------


@pytest.mark.windows_only
class TestPasteInterceptorShortcutDetection:
    """_PasteInterceptor._is_paste_shortcut correctly identifies paste keys."""

    def _make_interceptor(self) -> object:
        from press.clipboard import _PasteInterceptor  # type: ignore[attr-defined]

        return _PasteInterceptor()

    def test_ctrl_v_detected(self) -> None:
        interceptor = self._make_interceptor()
        interceptor._ctrl_held = True  # type: ignore[union-attr]
        key = _make_keycode("v")
        assert interceptor._is_paste_shortcut(key) is True  # type: ignore[union-attr]

    def test_ctrl_capital_v_not_detected(self) -> None:
        """Case-insensitive: only lowercase 'v' when ctrl held."""
        interceptor = self._make_interceptor()
        interceptor._ctrl_held = True  # type: ignore[union-attr]
        key = _make_keycode("V")
        # Capital V should not be treated as paste (char is 'V' not 'v')
        assert interceptor._is_paste_shortcut(key) is False  # type: ignore[union-attr]

    def test_ctrl_not_held_v_not_detected(self) -> None:
        interceptor = self._make_interceptor()
        interceptor._ctrl_held = False  # type: ignore[union-attr]
        key = _make_keycode("v")
        assert interceptor._is_paste_shortcut(key) is False  # type: ignore[union-attr]

    def test_shift_insert_detected(self) -> None:
        """Shift+Insert is detected as paste via duck-typed key.name == 'insert'."""
        interceptor = self._make_interceptor()
        interceptor._shift_held = True  # type: ignore[union-attr]
        key = _make_special_key("insert")
        assert interceptor._is_paste_shortcut(key) is True  # type: ignore[union-attr]

    def test_shift_not_held_insert_not_detected(self) -> None:
        interceptor = self._make_interceptor()
        interceptor._shift_held = False  # type: ignore[union-attr]
        key = _make_special_key("insert")
        assert interceptor._is_paste_shortcut(key) is False  # type: ignore[union-attr]

    def test_unrelated_key_not_detected(self) -> None:
        interceptor = self._make_interceptor()
        interceptor._ctrl_held = True  # type: ignore[union-attr]
        interceptor._shift_held = True  # type: ignore[union-attr]
        key = _make_keycode("c")  # Ctrl+C = copy, not paste
        assert interceptor._is_paste_shortcut(key) is False  # type: ignore[union-attr]


# ---------------------------------------------------------------------------
# _ClipboardMonitorWindow — _restoring flag prevents infinite loop
# ---------------------------------------------------------------------------


@pytest.mark.windows_only
class TestClipboardMonitorWindowRestoringFlag:
    """_on_clipboard_update ignores re-entrant calls when _restoring is True."""

    def test_restoring_flag_prevents_reentrance(self) -> None:
        from press.clipboard import _ClipboardMonitorWindow  # type: ignore[attr-defined]

        with patch("press.clipboard._win_set_text") as mock_set:
            monitor = _ClipboardMonitorWindow(lambda: "protected")
            monitor._restoring = True
            monitor._on_clipboard_update()
            mock_set.assert_not_called()

    def test_not_restoring_calls_win_set_text(self) -> None:
        from press.clipboard import _ClipboardMonitorWindow  # type: ignore[attr-defined]

        with patch("press.clipboard._win_set_text") as mock_set:
            monitor = _ClipboardMonitorWindow(lambda: "protected")
            monitor._restoring = False
            monitor._on_clipboard_update()
            mock_set.assert_called_once_with("protected")

    def test_restoring_flag_reset_after_update(self) -> None:
        from press.clipboard import _ClipboardMonitorWindow  # type: ignore[attr-defined]

        with patch("press.clipboard._win_set_text"):
            monitor = _ClipboardMonitorWindow(lambda: "protected")
            monitor._restoring = False
            monitor._on_clipboard_update()
            assert monitor._restoring is False
