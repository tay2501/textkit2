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
# _ClipboardMonitorWindow — its own restores must not re-trigger it
# ---------------------------------------------------------------------------


@pytest.mark.windows_only
class TestClipboardMonitorOwnWrites:
    """WM_CLIPBOARDUPDATE is *posted* for every change, the monitor's own
    restores included (Microsoft Learn, AddClipboardFormatListener), so it
    arrives after the restore returned.  Without recognising its own writes
    the monitor restored its own restore until the storm guard released the
    hold — one external copy released it within ~7 ms on real hardware."""

    _HWND = 0x1234

    def test_own_write_is_ignored(self) -> None:
        from press.clipboard import _ClipboardMonitorWindow  # type: ignore[attr-defined]

        with (
            patch("press.clipboard._win_set_text") as mock_set,
            patch("press.clipboard._user32") as u32,
        ):
            u32.GetClipboardOwner.return_value = self._HWND
            monitor = _ClipboardMonitorWindow(lambda: "protected")
            monitor._hwnd = self._HWND
            monitor._on_clipboard_update()
            mock_set.assert_not_called()

    def test_foreign_write_is_restored_as_the_monitor_window(self) -> None:
        from press.clipboard import _ClipboardMonitorWindow  # type: ignore[attr-defined]

        with (
            patch("press.clipboard._win_set_text") as mock_set,
            patch("press.clipboard._user32") as u32,
        ):
            u32.GetClipboardOwner.return_value = 0x9999
            monitor = _ClipboardMonitorWindow(lambda: "protected")
            monitor._hwnd = self._HWND
            monitor._on_clipboard_update()
            mock_set.assert_called_once_with("protected", owner=self._HWND)

    def test_own_writes_never_count_towards_a_storm(self) -> None:
        from press import clipboard
        from press.clipboard import _ClipboardMonitorWindow  # type: ignore[attr-defined]

        on_storm = MagicMock()
        with (
            patch("press.clipboard._win_set_text"),
            patch("press.clipboard._user32") as u32,
        ):
            u32.GetClipboardOwner.return_value = self._HWND
            monitor = _ClipboardMonitorWindow(lambda: "protected", on_storm)
            monitor._hwnd = self._HWND
            for _ in range(clipboard._STORM_LIMIT * 3):  # type: ignore[attr-defined]
                monitor._on_clipboard_update()
        on_storm.assert_not_called()

    def test_failed_restore_is_logged_not_raised(self, caplog: pytest.LogCaptureFixture) -> None:
        """An exception escaping a ctypes callback is only printed to stderr
        ("Exception ignored ...") and never reaches daemon.log."""
        from press.clipboard import _ClipboardMonitorWindow  # type: ignore[attr-defined]

        with (
            patch(
                "press.clipboard._win_set_text",
                side_effect=RuntimeError("Failed to open clipboard (error 5)"),
            ),
            caplog.at_level("WARNING", logger="press.daemon"),
        ):
            monitor = _ClipboardMonitorWindow(lambda: "protected")
            monitor._on_clipboard_update()

        assert "Failed to open clipboard (error 5)" in caplog.text
        assert "protected" not in caplog.text  # never log clipboard contents


# ---------------------------------------------------------------------------
# _ClipboardMonitorWindow — restore-storm detection (clipboard war)
# ---------------------------------------------------------------------------


@pytest.mark.windows_only
class TestClipboardMonitorStormDetection:
    """A restore war with another clipboard tool must trigger on_storm."""

    def test_rapid_restores_trigger_on_storm_and_stop_restoring(self) -> None:
        from press.clipboard import _ClipboardMonitorWindow  # type: ignore[attr-defined]

        on_storm = MagicMock()
        with patch("press.clipboard._win_set_text") as mock_set:
            monitor = _ClipboardMonitorWindow(lambda: "protected", on_storm)
            for _ in range(50):
                monitor._on_clipboard_update()

        on_storm.assert_called()
        assert mock_set.call_count < 50  # restores stop once the storm triggers

    def test_slow_restores_never_trigger(self) -> None:
        from press import clipboard
        from press.clipboard import _ClipboardMonitorWindow  # type: ignore[attr-defined]

        on_storm = MagicMock()
        fake_now = iter(float(i) for i in range(1000))  # 1 second between events
        with (
            patch("press.clipboard._win_set_text"),
            patch("time.monotonic", side_effect=lambda: next(fake_now)),
        ):
            monitor = _ClipboardMonitorWindow(lambda: "protected", on_storm)
            for _ in range(clipboard._STORM_LIMIT * 3):  # type: ignore[attr-defined]
                monitor._on_clipboard_update()

        on_storm.assert_not_called()


@pytest.mark.windows_only
class TestClipboardGuardConflictHandling:
    """The guard stands down and notifies its owner on a restore storm."""

    def test_conflict_releases_and_notifies(self) -> None:
        from press.clipboard import ClipboardGuard

        on_conflict = MagicMock()
        guard = ClipboardGuard(on_conflict=on_conflict)
        with (
            patch.object(guard, "_start_layer1"),
            patch.object(guard, "_start_layer2"),
            patch.object(guard, "_stop_layer1"),
            patch.object(guard, "_stop_layer2"),
        ):
            guard.engage("secret")
            guard._handle_conflict()

        assert guard.is_active is False
        on_conflict.assert_called_once()

    def test_conflict_without_callback_still_releases(self) -> None:
        from press.clipboard import ClipboardGuard

        guard = ClipboardGuard()
        with (
            patch.object(guard, "_start_layer1"),
            patch.object(guard, "_start_layer2"),
            patch.object(guard, "_stop_layer1"),
            patch.object(guard, "_stop_layer2"),
        ):
            guard.engage("secret")
            guard._handle_conflict()

        assert guard.is_active is False


@pytest.mark.windows_only
class TestMonitorWindowClassLifetime:
    """The monitor's window class outlives any one start()/stop() cycle.

    Window classes stay registered until the process exits (Microsoft Learn,
    RegisterClassExW), so the WNDPROC stored in the class must be a callback
    that lives as long as the process.  A per-start() callback left the class
    pointing at a freed ctypes thunk from the second hold onwards.
    """

    @staticmethod
    def _class_wndproc(hwnd: int) -> int:
        import ctypes

        from press import clipboard

        get_class_long = clipboard._user32.GetClassLongPtrW
        get_class_long.argtypes = [ctypes.c_void_p, ctypes.c_int]
        get_class_long.restype = ctypes.c_void_p
        return int(get_class_long(hwnd, -24))  # GCLP_WNDPROC

    def test_every_start_uses_the_process_lifetime_callback(self) -> None:
        import ctypes

        from press import clipboard

        expected = ctypes.cast(clipboard._WND_PROC, ctypes.c_void_p).value
        monitor = clipboard._ClipboardMonitorWindow(lambda: None)  # never restores
        for _ in range(2):
            monitor.start()
            assert monitor._hwnd is not None
            assert self._class_wndproc(monitor._hwnd) == expected
            thread = monitor._thread
            monitor.stop()
            assert thread is not None
            thread.join(timeout=2.0)
            assert not thread.is_alive()

    def test_start_raises_when_the_window_cannot_be_created(self) -> None:
        from press import clipboard

        monitor = clipboard._ClipboardMonitorWindow(lambda: None)
        with (
            patch.object(clipboard._user32, "CreateWindowExW", return_value=None),
            pytest.raises(RuntimeError, match="clipboard monitor window"),
        ):
            monitor.start()
        assert monitor._hwnd is None


@pytest.mark.windows_only
class TestClipboardGuardEngageFailure:
    def test_failed_layer_start_leaves_guard_inactive(self) -> None:
        from press.clipboard import ClipboardGuard

        guard = ClipboardGuard()
        with (
            patch.object(guard, "_start_layer1", side_effect=RuntimeError("no window")),
            patch.object(guard, "_start_layer2"),
            patch.object(guard, "_stop_layer1"),
            patch.object(guard, "_stop_layer2"),
            pytest.raises(RuntimeError),
        ):
            guard.engage("secret")
        assert guard.is_active is False


@pytest.mark.windows_only
class TestPasteInterceptorWritesAsTheMonitor:
    """Layer 2's pre-paste write must also be recognisable as the guard's own,
    or every Ctrl+V would feed Layer 1 another restore."""

    def test_layer2_is_armed_with_the_guards_writer(self) -> None:
        from press.clipboard import ClipboardGuard

        guard = ClipboardGuard()
        with patch.object(guard._interceptor, "start") as start:  # type: ignore[attr-defined]
            guard._start_layer2()  # type: ignore[attr-defined]
        start.assert_called_once_with(guard._get_protected, guard._write_protected)  # type: ignore[attr-defined]

    def test_write_protected_uses_the_monitor_window_as_owner(self) -> None:
        from press.clipboard import ClipboardGuard

        guard = ClipboardGuard()
        guard._monitor._hwnd = 0x1234  # type: ignore[attr-defined]
        with patch("press.clipboard._win_set_text") as mock_set:
            guard._write_protected("protected")  # type: ignore[attr-defined]
        mock_set.assert_called_once_with("protected", owner=0x1234)
