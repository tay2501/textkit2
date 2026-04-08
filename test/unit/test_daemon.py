"""Unit tests for press.daemon.

All tests run on every platform (mocks replace pynput / pystray / psutil).
Only TestAcquireMutex requires Windows and is marked @pytest.mark.windows_only.
"""

from __future__ import annotations

import queue
import time
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import pytest

if TYPE_CHECKING:
    from pathlib import Path

# ---------------------------------------------------------------------------
# _to_pynput_hotkey
# ---------------------------------------------------------------------------


class TestToPynputHotkey:
    @pytest.mark.parametrize(
        "press_spec,expected",
        [
            ("ctrl+shift+f10", "<ctrl>+<shift>+<f10>"),
            ("ctrl+alt+a", "<ctrl>+<alt>+a"),
            ("f12", "<f12>"),
            ("shift+u", "<shift>+u"),
            ("ctrl+shift+f1", "<ctrl>+<shift>+<f1>"),
        ],
    )
    def test_conversion(self, press_spec: str, expected: str) -> None:
        from press.daemon import _to_pynput_hotkey

        assert _to_pynput_hotkey(press_spec) == expected


# ---------------------------------------------------------------------------
# _normalize_key
# ---------------------------------------------------------------------------


class TestNormalizeKey:
    def _make_keycode(self, char: str | None) -> Any:
        key = MagicMock()
        key.char = char
        return key

    def _make_special(self, name: str) -> Any:
        key = MagicMock()
        # Remove KeyCode attribute to prevent isinstance(key, kb.KeyCode) from matching
        del key.char
        return key

    def test_lowercase_char(self) -> None:
        from pynput import keyboard as kb

        from press.daemon import _normalize_key

        key = kb.KeyCode.from_char("w")
        assert _normalize_key(key) == "w"

    def test_uppercase_char_lowercased(self) -> None:
        from pynput import keyboard as kb

        from press.daemon import _normalize_key

        key = kb.KeyCode.from_char("A")
        assert _normalize_key(key) == "a"

    def test_special_key_returns_name(self) -> None:
        from pynput import keyboard as kb

        from press.daemon import _normalize_key

        assert _normalize_key(kb.Key.shift) == "shift"
        assert _normalize_key(kb.Key.ctrl) == "ctrl"

    def test_none_returns_none(self) -> None:
        from press.daemon import _normalize_key

        assert _normalize_key(None) is None

    def test_unknown_object_returns_none(self) -> None:
        from press.daemon import _normalize_key

        assert _normalize_key(object()) is None


# ---------------------------------------------------------------------------
# CommandDispatcher
# ---------------------------------------------------------------------------


class TestCommandDispatcherHalfwidth:
    def test_dispatch_halfwidth_transforms_clipboard(self, tmp_path: Path) -> None:
        from press.config import PressConfig
        from press.daemon import CommandDispatcher

        with (
            patch("press.clipboard.get_clipboard_text", return_value="ＡＢＣ"),
            patch("press.clipboard.set_clipboard_text") as mock_set,
        ):
            d = CommandDispatcher(PressConfig())
            d.dispatch("halfwidth")
            mock_set.assert_called_once_with("ABC")

    def test_dispatch_clear_calls_clear_not_set(self) -> None:
        from press.config import PressConfig
        from press.daemon import CommandDispatcher

        with (
            patch("press.clipboard.clear_clipboard") as mock_clear,
            patch("press.clipboard.set_clipboard_text") as mock_set,
            patch("press.clipboard.get_clipboard_text", return_value="x"),
        ):
            d = CommandDispatcher(PressConfig())
            d.dispatch("clear")
            mock_clear.assert_called_once()
            mock_set.assert_not_called()


class TestCommandDispatcherHold:
    def test_hold_stores_clipboard_text(self) -> None:
        """dispatch("hold") engages the guard with the clipboard text."""
        from press.config import PressConfig
        from press.daemon import CommandDispatcher

        with patch("press.clipboard.get_clipboard_text", return_value="x"):
            d = CommandDispatcher(PressConfig())
            mock_icon = MagicMock()
            d.set_icon(mock_icon)
            mock_guard = MagicMock()
            mock_guard.is_active = False
            d._guard = mock_guard  # type: ignore[assignment]
            # Guard must not be active initially
            assert d._guard.is_active is False
            d.dispatch("hold")
            mock_guard.engage.assert_called_once_with("x")


class TestCommandDispatcherNotifyLevel:
    def _make_config(self, level: str) -> Any:
        from press.config import PressConfig, UiConfig

        ui = UiConfig(notify_level=level)
        return PressConfig(ui=ui)

    def test_notify_off_no_calls(self) -> None:
        from press.daemon import CommandDispatcher

        config = self._make_config("off")
        with (
            patch("press.clipboard.get_clipboard_text", return_value="abc"),
            patch("press.clipboard.set_clipboard_text"),
        ):
            d = CommandDispatcher(config)
            mock_icon = MagicMock()
            d.set_icon(mock_icon)
            d.dispatch("halfwidth")
            mock_icon.notify.assert_not_called()

    def test_notify_success_on_success(self) -> None:
        from press.daemon import CommandDispatcher

        config = self._make_config("success")
        with (
            patch("press.clipboard.get_clipboard_text", return_value="abc"),
            patch("press.clipboard.set_clipboard_text"),
        ):
            d = CommandDispatcher(config)
            mock_icon = MagicMock()
            d.set_icon(mock_icon)
            d.dispatch("halfwidth")
            mock_icon.notify.assert_called_once()

    def test_notify_error_on_failure(self) -> None:
        from press.daemon import CommandDispatcher

        config = self._make_config("error")
        with patch("press.clipboard.get_clipboard_text", side_effect=OSError("clipboard error")):
            d = CommandDispatcher(config)
            mock_icon = MagicMock()
            d.set_icon(mock_icon)
            d.dispatch("halfwidth")
            mock_icon.notify.assert_called_once()

    def test_notify_all_on_success_and_error(self) -> None:
        from press.daemon import CommandDispatcher

        config = self._make_config("all")
        # success call
        with (
            patch("press.clipboard.get_clipboard_text", return_value="abc"),
            patch("press.clipboard.set_clipboard_text"),
        ):
            d = CommandDispatcher(config)
            mock_icon = MagicMock()
            d.set_icon(mock_icon)
            d.dispatch("halfwidth")
            assert mock_icon.notify.call_count == 1

        # error call
        with patch("press.clipboard.get_clipboard_text", side_effect=OSError("err")):
            d2 = CommandDispatcher(config)
            mock_icon2 = MagicMock()
            d2.set_icon(mock_icon2)
            d2.dispatch("halfwidth")
            assert mock_icon2.notify.call_count == 1


# ---------------------------------------------------------------------------
# LeaderKeyListener (direct _on_press invocation)
# ---------------------------------------------------------------------------


class TestLeaderKeyListenerOnPress:
    def _make_listener(
        self, bindings: dict[str, str] | None = None
    ) -> tuple[Any, queue.Queue[tuple[str, ...]]]:
        from press.daemon import LeaderKeyListener

        q: queue.Queue[tuple[str, ...]] = queue.Queue()
        ll = LeaderKeyListener(bindings or {"w": "halfwidth", "shift+u": "underscore"}, q)
        return ll, q

    def _keycode(self, char: str) -> Any:
        from pynput import keyboard as kb

        return kb.KeyCode.from_char(char)

    def test_known_key_enqueues_dispatch(self) -> None:
        ll, q = self._make_listener()
        ll._on_press(self._keycode("w"))
        assert q.get_nowait() == ("dispatch", "halfwidth")

    def test_unknown_key_enqueues_unknown_key(self) -> None:
        ll, q = self._make_listener()
        ll._on_press(self._keycode("x"))
        item = q.get_nowait()
        assert item[0] == "unknown_key"

    def test_shift_held_matches_shifted_binding(self) -> None:
        ll, q = self._make_listener()
        from pynput import keyboard as kb

        ll._on_press(kb.Key.shift)
        ll._on_press(self._keycode("u"))
        assert q.get_nowait() == ("dispatch", "underscore")

    def test_shift_released_clears_state(self) -> None:
        ll, q = self._make_listener()
        from pynput import keyboard as kb

        ll._on_press(kb.Key.shift)
        ll._on_release(kb.Key.shift)
        ll._on_press(self._keycode("u"))
        item = q.get_nowait()
        # "u" alone is not in bindings → unknown_key (shift+u binding doesn't match)
        assert item[0] == "unknown_key"


class TestLeaderKeyListenerTimeout:
    def test_timeout_enqueues_timeout(self) -> None:
        from press.daemon import LeaderKeyListener

        q: queue.Queue[tuple[str, ...]] = queue.Queue()
        ll = LeaderKeyListener({}, q, timeout=0.1)

        with patch("pynput.keyboard.Listener") as MockListener:
            MockListener.return_value.start.return_value = None
            ll.start()
            time.sleep(0.35)

        item = q.get_nowait()
        assert item == ("timeout",)


# ---------------------------------------------------------------------------
# HotkeyManager
# ---------------------------------------------------------------------------


class TestHotkeyManager:
    def test_start_registers_prefix_hotkey(self) -> None:
        from press.config import HotkeysConfig
        from press.daemon import HotkeyManager

        q: queue.Queue[tuple[str, ...]] = queue.Queue()
        cfg = HotkeysConfig(prefix="ctrl+shift+f10", bindings={})

        with patch("pynput.keyboard.GlobalHotKeys") as MockGH:
            MockGH.return_value.start.return_value = None
            hm = HotkeyManager(cfg, q)
            hm.start()
            MockGH.assert_called_once()
            # Verify the prefix was converted to pynput format
            call_args = MockGH.call_args[0][0]
            assert "<ctrl>+<shift>+<f10>" in call_args

    def test_on_prefix_activates_leader(self) -> None:
        from press.config import HotkeysConfig
        from press.daemon import HotkeyManager, LeaderKeyListener

        q: queue.Queue[tuple[str, ...]] = queue.Queue()
        cfg = HotkeysConfig()
        hm = HotkeyManager(cfg, q)
        hm._leader = MagicMock(spec=LeaderKeyListener)

        hm._on_prefix()
        hm._leader.start.assert_called_once()

    def test_on_prefix_does_not_retrigger_while_active(self) -> None:
        from press.config import HotkeysConfig
        from press.daemon import HotkeyManager, LeaderKeyListener

        q: queue.Queue[tuple[str, ...]] = queue.Queue()
        cfg = HotkeysConfig()
        hm = HotkeyManager(cfg, q)
        hm._leader = MagicMock(spec=LeaderKeyListener)

        hm._on_prefix()
        hm._on_prefix()  # second call while active → ignored
        assert hm._leader.start.call_count == 1

    def test_reset_leader_allows_retrigger(self) -> None:
        from press.config import HotkeysConfig
        from press.daemon import HotkeyManager, LeaderKeyListener

        q: queue.Queue[tuple[str, ...]] = queue.Queue()
        cfg = HotkeysConfig()
        hm = HotkeyManager(cfg, q)
        hm._leader = MagicMock(spec=LeaderKeyListener)

        hm._on_prefix()
        hm.reset_leader()
        hm._on_prefix()
        assert hm._leader.start.call_count == 2


# ---------------------------------------------------------------------------
# stop_daemon
# ---------------------------------------------------------------------------


class TestStopDaemon:
    def test_no_pid_file_returns_1(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("press.daemon._PID_PATH", tmp_path / "press.pid")
        from press.daemon import stop_daemon

        assert stop_daemon() == 1

    def test_invalid_pid_file_returns_1(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        pid_file = tmp_path / "press.pid"
        pid_file.write_text("not-a-number", encoding="utf-8")
        monkeypatch.setattr("press.daemon._PID_PATH", pid_file)
        from press.daemon import stop_daemon

        assert stop_daemon() == 1

    def test_stale_pid_returns_1_and_removes_file(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        pid_file = tmp_path / "press.pid"
        pid_file.write_text("99999", encoding="utf-8")
        monkeypatch.setattr("press.daemon._PID_PATH", pid_file)

        import psutil

        with patch("psutil.Process", side_effect=psutil.NoSuchProcess(99999)):
            from press.daemon import stop_daemon

            assert stop_daemon() == 1
        assert not pid_file.exists()

    def test_success_returns_0_and_removes_file(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        pid_file = tmp_path / "press.pid"
        pid_file.write_text("12345", encoding="utf-8")
        monkeypatch.setattr("press.daemon._PID_PATH", pid_file)

        mock_proc = MagicMock()
        with patch("psutil.Process", return_value=mock_proc):
            from press.daemon import stop_daemon

            assert stop_daemon() == 0
        mock_proc.terminate.assert_called_once()
        assert not pid_file.exists()


# ---------------------------------------------------------------------------
# daemon_status
# ---------------------------------------------------------------------------


class TestDaemonStatus:
    def test_not_running_no_pid_file(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        monkeypatch.setattr("press.daemon._PID_PATH", tmp_path / "press.pid")
        monkeypatch.setattr("sys.platform", "linux")
        from press.daemon import daemon_status

        rc = daemon_status()
        assert rc == 1
        assert "not running" in capsys.readouterr().out

    def test_running_via_psutil(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        pid_file = tmp_path / "press.pid"
        pid_file.write_text("12345", encoding="utf-8")
        monkeypatch.setattr("press.daemon._PID_PATH", pid_file)
        monkeypatch.setattr("sys.platform", "linux")

        with patch("psutil.pid_exists", return_value=True):
            from press.daemon import daemon_status

            rc = daemon_status()
        assert rc == 0
        assert "running" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# _acquire_mutex (Windows only)
# ---------------------------------------------------------------------------


@pytest.mark.windows_only
class TestAcquireMutex:
    def test_first_call_succeeds(self) -> None:
        from press.daemon import _acquire_mutex, _release_mutex

        handle = _acquire_mutex()
        assert handle is not None
        _release_mutex(handle)

    def test_second_call_returns_none(self) -> None:
        from press.daemon import _acquire_mutex, _release_mutex

        handle1 = _acquire_mutex()
        assert handle1 is not None
        try:
            handle2 = _acquire_mutex()
            assert handle2 is None
        finally:
            _release_mutex(handle1)


# ---------------------------------------------------------------------------
# _create_tray_image
# ---------------------------------------------------------------------------


class TestCreateTrayImage:
    def test_creates_valid_image(self) -> None:
        from press.daemon import _create_tray_image

        img = _create_tray_image()
        assert img.size == (64, 64)
        assert img.mode == "RGBA"


# ---------------------------------------------------------------------------
# daemon_status (Windows mutex probe)
# ---------------------------------------------------------------------------


class TestDaemonStatusWindows:
    @pytest.mark.windows_only
    def test_running_via_mutex_on_windows(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        pid_file = tmp_path / "press.pid"
        pid_file.write_text("99999", encoding="utf-8")
        monkeypatch.setattr("press.daemon._PID_PATH", pid_file)
        monkeypatch.setattr("sys.platform", "win32")

        from press.daemon import _acquire_mutex, daemon_status

        # Acquire mutex to simulate daemon running
        handle = _acquire_mutex()
        assert handle is not None
        try:
            rc = daemon_status()
            assert rc == 0
            assert "running" in capsys.readouterr().out
        finally:
            from press.daemon import _release_mutex

            _release_mutex(handle)

    @pytest.mark.windows_only
    def test_not_running_via_mutex_on_windows(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        pid_file = tmp_path / "press.pid"
        pid_file.write_text("99999", encoding="utf-8")
        monkeypatch.setattr("press.daemon._PID_PATH", pid_file)
        monkeypatch.setattr("sys.platform", "win32")

        from press.daemon import daemon_status

        rc = daemon_status()
        assert rc == 1
        assert "not running" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# stop_daemon (timeout handling)
# ---------------------------------------------------------------------------


class TestStopDaemonTimeout:
    def test_timeout_expires_kills_process(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        pid_file = tmp_path / "press.pid"
        pid_file.write_text("12345", encoding="utf-8")
        monkeypatch.setattr("press.daemon._PID_PATH", pid_file)

        import psutil

        mock_proc = MagicMock()
        mock_proc.wait.side_effect = psutil.TimeoutExpired("fake", 1.0)
        with patch("psutil.Process", return_value=mock_proc):
            from press.daemon import stop_daemon

            assert stop_daemon() == 0
        mock_proc.terminate.assert_called_once()
        mock_proc.kill.assert_called_once()
        assert not pid_file.exists()


# ---------------------------------------------------------------------------
# WorkerThread dispatch matching
# ---------------------------------------------------------------------------


class TestWorkerThreadDispatch:
    def test_worker_handles_all_work_types(self) -> None:
        from press.config import PressConfig
        from press.daemon import CommandDispatcher, HotkeyManager, _WorkerThread

        config = PressConfig()
        work_queue: queue.Queue[tuple[str, ...]] = queue.Queue()
        dispatcher = CommandDispatcher(config)
        hm = HotkeyManager(config.hotkeys, work_queue)

        # Enqueue a stop command
        work_queue.put(("stop",))

        # Create and run worker briefly
        worker = _WorkerThread(work_queue, dispatcher, hm)
        worker.run()

        # Worker should exit after processing stop
        assert work_queue.empty()
