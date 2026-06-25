"""press daemon — system-tray icon + global-hotkey listener (Windows only).

This module is imported lazily: only when ``press daemon <action>`` is invoked.
All third-party imports (pystray, pynput, Pillow, psutil) live inside
functions/methods so that CLI-only usage works without the ``daemon`` extra.
"""

from __future__ import annotations

import ctypes
import logging
import os
import queue
import re
import sys
import threading
from datetime import UTC
from pathlib import Path
from typing import TYPE_CHECKING, Any, override

if TYPE_CHECKING:
    from collections.abc import Callable

    import pystray
    from PIL.Image import Image
    from pynput import keyboard

    from press.clipboard import ClipboardGuard
    from press.config import HotkeysConfig, PressConfig

__all__ = ["daemon_logs", "daemon_status", "run_daemon", "stop_daemon"]

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MUTEX_NAME = "Global\\press_daemon_singleton"
_LEADER_TIMEOUT = 2.0  # seconds to wait for a binding key after prefix
_ICON_SIZE = 64  # tray icon size in pixels

_PID_PATH: Path = Path(os.environ.get("APPDATA", str(Path.home()))) / "press" / "press.pid"
_LOG_PATH: Path = Path(os.environ.get("APPDATA", str(Path.home()))) / "press" / "daemon.log"
_STATUS_PATH: Path = Path(os.environ.get("APPDATA", str(Path.home()))) / "press" / "status.json"
_LOG_MAX_BYTES = 5 * 1024 * 1024  # 5 MB per SPEC §15
_LOG_BACKUP_COUNT = 3

# Module-level logger — handlers are added by _setup_logging() at daemon start.
_log = logging.getLogger("press.daemon")

# Log line format written by _setup_logging's Formatter:
#   2026-05-15T09:30:00 INFO     message text here
_LOG_LINE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})\s+(\w+)\s+(.*)$")
_LEVEL_MIN: dict[str, int] = {
    "debug": 10,
    "info": 20,
    "warning": 30,
    "error": 40,
    "critical": 50,
    "all": 0,
}

# Token set for _to_pynput_hotkey: these need angle-bracket wrapping
_MODIFIER_TOKENS = frozenset({"ctrl", "shift", "alt", "cmd", "win", "meta"})


# ---------------------------------------------------------------------------
# Helpers (platform-independent logic)
# ---------------------------------------------------------------------------


def _create_tray_image(holding: bool = False) -> Image:
    """Return a 64x64 RGBA PIL image used as the system-tray icon.

    Args:
        holding: When ``True``, the background is red to indicate hold state.
    """
    from PIL import Image, ImageDraw, ImageFont

    bg_color = (180, 30, 30, 255) if holding else (30, 30, 30, 255)
    img = Image.new("RGBA", (_ICON_SIZE, _ICON_SIZE), bg_color)
    draw = ImageDraw.Draw(img)
    font = ImageFont.load_default(size=40)
    bbox = draw.textbbox((0, 0), "P", font=font)
    x = (_ICON_SIZE - (bbox[2] - bbox[0])) // 2 - bbox[0]
    y = (_ICON_SIZE - (bbox[3] - bbox[1])) // 2 - bbox[1]
    draw.text((x, y), "P", fill=(255, 255, 255, 255), font=font)
    return img


def _to_pynput_hotkey(press_spec: str) -> str:
    """Convert a press-style hotkey spec to pynput format.

    Example::

        _to_pynput_hotkey("ctrl+shift+f10")  # "<ctrl>+<shift>+<f10>"
        _to_pynput_hotkey("ctrl+a")           # "<ctrl>+a"

    Single printable characters are left unbracketed; modifiers and function
    keys are wrapped in ``<>``.
    """
    parts: list[str] = []
    for token in press_spec.lower().split("+"):
        if token in _MODIFIER_TOKENS or (token.startswith("f") and token[1:].isdigit()):
            parts.append(f"<{token}>")
        else:
            parts.append(token)
    return "+".join(parts)


def _normalize_key(key: object) -> str | None:
    """Map a pynput key object to a config-binding key name.

    Returns ``None`` for keys that have no printable representation.
    """
    from pynput import keyboard as kb

    if isinstance(key, kb.KeyCode):
        return str(key.char).lower() if key.char else None
    if isinstance(key, kb.Key):
        return str(key.name)  # e.g. "shift", "ctrl", "f10"
    return None


# ---------------------------------------------------------------------------
# Logging helpers
# ---------------------------------------------------------------------------


def _setup_logging() -> None:
    """Configure rotating file logging for the daemon (idempotent)."""
    import logging.handlers

    if _log.handlers:
        return
    _log.setLevel(logging.DEBUG)
    _LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    handler = logging.handlers.RotatingFileHandler(
        _LOG_PATH,
        maxBytes=_LOG_MAX_BYTES,
        backupCount=_LOG_BACKUP_COUNT,
        encoding="utf-8",
    )
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s %(levelname)-8s %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
        )
    )
    _log.addHandler(handler)


# ---------------------------------------------------------------------------
# Status file helpers
# ---------------------------------------------------------------------------


def _write_status_file(data: dict[str, object]) -> None:
    """Persist daemon state to *_STATUS_PATH* as JSON."""
    import json

    _STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    _STATUS_PATH.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def _read_status_file() -> dict[str, object] | None:
    """Load the status file, returning ``None`` on missing or parse error."""
    import json

    try:
        return dict(json.loads(_STATUS_PATH.read_text(encoding="utf-8")))
    except (FileNotFoundError, json.JSONDecodeError):
        return None


# ---------------------------------------------------------------------------
# Mutex helpers (Windows only)
# ---------------------------------------------------------------------------


def _acquire_mutex() -> int | None:
    """Acquire the named singleton mutex and return its HANDLE.

    Returns ``None`` when another instance already holds the mutex, or on
    non-Windows platforms.
    """
    if sys.platform == "win32":
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.CreateMutexW(None, True, _MUTEX_NAME)
        if kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
            if handle:
                kernel32.CloseHandle(handle)
            return None
        return int(handle)
    return None  # pragma: no cover


def _release_mutex(handle: int) -> None:
    """Close the mutex HANDLE."""
    if sys.platform == "win32":
        ctypes.windll.kernel32.CloseHandle(handle)


# ---------------------------------------------------------------------------
# CommandDispatcher
# ---------------------------------------------------------------------------


class CommandDispatcher:
    """Execute clipboard transform commands and optionally notify via the tray.

    Args:
        config: A :class:`~press.config.PressConfig` instance.
    """

    def __init__(self, config: PressConfig) -> None:
        self._config = config
        self._icon: pystray.Icon | None = None
        # Dual-layer clipboard guard (Windows only; None on other platforms)
        self._guard: ClipboardGuard | None = None
        if sys.platform == "win32":
            from press.clipboard import ClipboardGuard as _Guard

            self._guard = _Guard(config.hold)

    def set_icon(self, icon: pystray.Icon) -> None:
        """Bind the tray icon used for notifications."""
        self._icon = icon

    # ------------------------------------------------------------------
    # Public

    def dispatch(self, command: str) -> None:
        """Run *command* on the clipboard in-place.

        Reads the current clipboard text, applies the named transform, and
        writes the result back.  Notifications are emitted according to
        ``config.ui.notify_level``.
        """
        from press.clipboard import clear_clipboard, get_clipboard_text, set_clipboard_text

        try:
            if command == "clear":
                clear_clipboard()
                self._notify_success(command, "")
                return
            if command == "hold":
                self._toggle_hold()
                return
            text = get_clipboard_text()
            result = self._transform(command, text)
            set_clipboard_text(result)
            self._notify_success(command, result)
        except Exception as exc:
            self._notify_error(command, str(exc))

    # ------------------------------------------------------------------
    # Internal

    def _transform(self, command: str, text: str) -> str:
        import importlib
        from typing import cast

        from press.commands import (
            PARAMETRIC_ALIASES,
            PARAMETRIC_COMMAND_INDEX,
            SIMPLE_COMMAND_INDEX,
        )

        # Resolve parametric aliases (e.g. "jf" → "json-format")
        command = PARAMETRIC_ALIASES.get(command, command)

        # Simple commands: resolved dynamically via the central registry
        if command in SIMPLE_COMMAND_INDEX:
            spec = SIMPLE_COMMAND_INDEX[command]
            fn = cast(
                "Callable[[str], str]",
                getattr(importlib.import_module(spec.module), spec.fn),
            )
            return fn(text)

        # Parametric commands: registry-driven dispatch with optional config kwargs
        if command in PARAMETRIC_COMMAND_INDEX:
            spec_p = PARAMETRIC_COMMAND_INDEX[command]
            fn_p = cast(
                "Callable[..., str]",
                getattr(importlib.import_module(spec_p.module), spec_p.fn),
            )
            kwargs: dict[str, Any] = (
                spec_p.daemon_kwargs(self._config) if spec_p.daemon_kwargs is not None else {}
            )
            return fn_p(text, **kwargs)

        # Special commands that require internal helpers
        match command:
            case "dict":
                return self._run_dict(text, reverse=False)
            case "dict_reverse":
                return self._run_dict(text, reverse=True)
            case _:
                raise ValueError(f"unknown command: {command!r}")

    def _run_dict(self, text: str, *, reverse: bool) -> str:
        from press.dictionary import default_dict_path
        from press.transforms.dictionary import dict_forward, dict_reverse, load_tsv

        cfg = self._config.dictionary
        paths = cfg.resolved_paths()
        path = paths[0] if paths else default_dict_path()
        table = load_tsv(path)
        return dict_reverse(text, table=table) if reverse else dict_forward(text, table=table)

    def notify_error(self, command: str, message: str) -> None:
        """Deliver an error notification; public entry point for external callers."""
        self._notify_error(command, message)

    def _notify_success(self, command: str, _result: str) -> None:
        if self._config.ui.notify_level in ("success", "all"):
            self._notify("press", f"[{command}] done")

    def _notify_error(self, command: str, message: str) -> None:
        if self._config.ui.notify_level in ("error", "all"):
            self._notify(f"press: {command} failed", message[:120])

    def _notify(self, title: str, message: str) -> None:
        if self._icon is None:
            return
        import contextlib

        with contextlib.suppress(Exception):
            self._icon.notify(message, title)

    def _toggle_hold(self) -> None:
        """Toggle dual-layer clipboard guard and update the tray icon."""
        if self._guard is None:
            return  # non-Windows: no-op

        if not self._guard.is_active:
            from press.clipboard import get_clipboard_text

            text = get_clipboard_text()
            self._guard.engage(text)
            self._update_icon(holding=True)
            self._notify_success("hold", "")
        else:
            self._guard.release()
            self._update_icon(holding=False)
            self._notify_success("hold-release", "")

    def _update_icon(self, *, holding: bool) -> None:
        """Swap the tray icon to reflect hold state."""
        if self._icon is None or not self._config.ui.hold_icon:
            return
        import contextlib

        with contextlib.suppress(Exception):
            self._icon.icon = _create_tray_image(holding=holding)


# ---------------------------------------------------------------------------
# LeaderKeyListener
# ---------------------------------------------------------------------------


class LeaderKeyListener:
    """Capture the next keypress after the prefix hotkey fires.

    After :meth:`start` is called, the listener waits up to *timeout* seconds
    for a key press that matches a binding entry.  Results are enqueued:

    - ``("dispatch", command)`` — binding matched, run *command*
    - ``("unknown_key", key_name)`` — key pressed but not in bindings
    - ``("timeout",)`` — no key pressed within the timeout window

    Args:
        bindings: Mapping of key names (e.g. ``"w"``, ``"shift+u"``) to
            command names (e.g. ``"halfwidth"``).
        work_queue: Queue shared with the worker thread.
        timeout: Seconds to wait before emitting a timeout item.
    """

    def __init__(
        self,
        bindings: dict[str, str],
        work_queue: queue.Queue[tuple[str, ...]],
        timeout: float = _LEADER_TIMEOUT,
    ) -> None:
        self._bindings = bindings
        self._queue = work_queue
        self._timeout = timeout
        self._listener: keyboard.Listener | None = None
        self._shift_held = False
        self._done = threading.Event()

    def start(self) -> None:
        """Begin listening for the next meaningful keypress."""
        from pynput import keyboard as kb

        self._done.clear()
        self._shift_held = False

        self._listener = kb.Listener(
            on_press=self._on_press,
            on_release=self._on_release,
        )
        self._listener.start()

        watcher = threading.Thread(target=self._timeout_watcher, daemon=True)
        watcher.start()

    def _timeout_watcher(self) -> None:
        self._done.wait(timeout=self._timeout)
        if not self._done.is_set():
            self._queue.put(("timeout",))
            self._stop()

    def _on_press(self, key: object) -> None:
        from pynput import keyboard as kb

        # Track shift state without treating it as a binding key
        if key in (kb.Key.shift, kb.Key.shift_l, kb.Key.shift_r):
            self._shift_held = True
            return

        # Ignore other standalone modifiers (ctrl, alt, …)
        char = _normalize_key(key)
        if char is None or char in {"ctrl", "alt", "cmd", "meta", "win"}:
            return

        binding_key = f"shift+{char}" if self._shift_held else char
        if binding_key in self._bindings:
            self._queue.put(("dispatch", self._bindings[binding_key]))
        else:
            self._queue.put(("unknown_key", binding_key))

        self._done.set()
        self._stop()

    def _on_release(self, key: object) -> None:
        from pynput import keyboard as kb

        if key in (kb.Key.shift, kb.Key.shift_l, kb.Key.shift_r):
            self._shift_held = False

    def _stop(self) -> None:
        if self._listener is not None:
            self._listener.stop()
            self._listener = None


# ---------------------------------------------------------------------------
# HotkeyManager
# ---------------------------------------------------------------------------


class HotkeyManager:
    """Manage the prefix GlobalHotKeys listener and leader-key state machine.

    Args:
        config: A :class:`~press.config.HotkeysConfig` instance.
        work_queue: Queue shared with the worker thread.
    """

    def __init__(
        self,
        config: HotkeysConfig,
        work_queue: queue.Queue[tuple[str, ...]],
    ) -> None:
        self._config = config
        self._queue = work_queue
        self._hotkey_listener: keyboard.GlobalHotKeys | None = None
        self._leader: LeaderKeyListener | None = None
        self._leader_active = False
        self._lock = threading.Lock()

    def start(self) -> None:
        """Start the GlobalHotKeys listener in a background daemon thread."""
        from pynput import keyboard as kb

        self._leader = LeaderKeyListener(self._config.bindings, self._queue)
        pynput_key = _to_pynput_hotkey(self._config.prefix)
        self._hotkey_listener = kb.GlobalHotKeys({pynput_key: self._on_prefix})
        self._hotkey_listener.start()

    def stop(self) -> None:
        """Stop the GlobalHotKeys listener."""
        if self._hotkey_listener is not None:
            self._hotkey_listener.stop()
            self._hotkey_listener = None

    def reset_leader(self) -> None:
        """Re-arm the prefix hotkey after a leader sequence completes."""
        with self._lock:
            self._leader_active = False

    def _on_prefix(self) -> None:
        """Called from the pynput OS thread — only set state, never do I/O."""
        with self._lock:
            if self._leader_active:
                return  # ignore re-trigger while waiting for binding key
            self._leader_active = True
        if self._leader is not None:
            self._leader.start()


# ---------------------------------------------------------------------------
# WorkerThread
# ---------------------------------------------------------------------------


class _WorkerThread(threading.Thread):
    """Drain the work queue and execute commands sequentially."""

    def __init__(
        self,
        work_queue: queue.Queue[tuple[str, ...]],
        dispatcher: CommandDispatcher,
        hotkey_manager: HotkeyManager,
    ) -> None:
        super().__init__(name="press-worker", daemon=True)
        self._queue = work_queue
        self._dispatcher = dispatcher
        self._hm = hotkey_manager

    @override
    def run(self) -> None:
        while True:
            item = self._queue.get()
            match item:
                case ("dispatch", command):
                    self._hm.reset_leader()
                    self._dispatcher.dispatch(str(command))
                case ("timeout",):
                    self._hm.reset_leader()
                case ("unknown_key", key):
                    self._hm.reset_leader()
                    self._dispatcher.notify_error("hotkey", f"no binding for: {key!r}")
                case ("stop",):
                    break
                case _:
                    pass
            self._queue.task_done()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def daemon_logs(
    lines: int | None = 50,
    *,
    follow: bool = False,
    level: str = "all",
    as_json: bool = False,
) -> int:
    """Print entries from the daemon log file.

    Args:
        lines: Number of tail lines to show, or ``None`` to show all.
        follow: If ``True``, stream new entries until Ctrl+C.
        level: Minimum level to display (``debug``/``info``/``warning``/``error``/``all``).
        as_json: Emit one JSON object per line (NDJSON) instead of plain text.

    Returns:
        0 on success, 1 if the log file does not exist.
    """
    import json as _json
    import time

    if not _LOG_PATH.exists():
        print(f"press daemon: log file not found: {_LOG_PATH}", file=sys.stderr)
        print("press daemon: start the daemon first to create a log file", file=sys.stderr)
        return 1

    min_level = _LEVEL_MIN.get(level.lower(), 0)

    def _parse(raw: str) -> tuple[str, str, str] | None:
        m = _LOG_LINE_RE.match(raw.rstrip("\n\r"))
        if not m:
            return None
        return m.group(1), m.group(2), m.group(3)

    def _passes(lvl: str) -> bool:
        return _LEVEL_MIN.get(lvl.lower(), 0) >= min_level

    def _emit(ts: str, lvl: str, msg: str) -> None:
        if as_json:
            print(_json.dumps({"ts": ts, "level": lvl, "msg": msg}))
        else:
            print(f"{ts} {lvl:<8} {msg}")

    with _LOG_PATH.open(encoding="utf-8", errors="replace") as fh:
        all_lines = fh.readlines()

    tail = all_lines[-lines:] if lines is not None else all_lines
    for raw in tail:
        parsed = _parse(raw)
        if parsed and _passes(parsed[1]):
            _emit(*parsed)

    if not follow:
        return 0

    print(f"Following {_LOG_PATH} — press Ctrl+C to stop", file=sys.stderr)
    try:
        with _LOG_PATH.open(encoding="utf-8", errors="replace") as fh:
            fh.seek(0, 2)  # jump to end
            while True:
                raw = fh.readline()
                if raw:
                    parsed = _parse(raw)
                    if parsed and _passes(parsed[1]):
                        _emit(*parsed)
                        sys.stdout.flush()
                else:
                    time.sleep(0.1)
    except KeyboardInterrupt:
        pass
    return 0


def run_daemon(config_path: Path | None = None) -> None:
    """Start the press daemon (blocking until quit from the tray menu).

    Args:
        config_path: Optional explicit path to the config TOML.  Defaults to
            ``%APPDATA%\\press\\config.toml``.

    Raises:
        SystemExit(1): On non-Windows or when another instance is already
            running.
    """
    if sys.platform != "win32":
        print("press daemon: error: only supported on Windows", file=sys.stderr)
        sys.exit(1)

    import pystray

    from press.config import load_config

    _setup_logging()

    config = load_config(config_path)

    mutex_handle = _acquire_mutex()
    if mutex_handle is None:
        print(
            "press daemon: error: another instance is already running",
            file=sys.stderr,
        )
        sys.exit(1)

    from datetime import datetime

    _PID_PATH.parent.mkdir(parents=True, exist_ok=True)
    _PID_PATH.write_text(str(os.getpid()), encoding="utf-8")

    import contextlib
    from importlib.metadata import version as _pkg_version

    _ver = "unknown"
    with contextlib.suppress(Exception):
        _ver = _pkg_version("press")

    _write_status_file(
        {
            "pid": os.getpid(),
            "started_at": datetime.now(UTC).astimezone().isoformat(timespec="seconds"),
            "version": _ver,
            "restart_count": 0,
            "state": "running",
        }
    )
    _log.info("daemon started pid=%d version=%s", os.getpid(), _ver)

    work_queue: queue.Queue[tuple[str, ...]] = queue.Queue()
    dispatcher = CommandDispatcher(config)
    hm = HotkeyManager(config.hotkeys, work_queue)
    worker = _WorkerThread(work_queue, dispatcher, hm)

    def _setup(icon: pystray.Icon) -> None:
        dispatcher.set_icon(icon)
        hm.start()
        worker.start()
        if config.ui.startup_notification:
            icon.notify("press daemon started", "press")

    def _on_quit(icon: pystray.Icon, _item: pystray.MenuItem) -> None:
        hm.stop()
        work_queue.put(("stop",))
        _PID_PATH.unlink(missing_ok=True)
        icon.stop()

    menu = pystray.Menu(
        pystray.MenuItem("press daemon", None, enabled=False),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Quit", _on_quit),
    )

    icon = pystray.Icon(
        name="press",
        icon=_create_tray_image(),
        title="press",
        menu=menu,
    )

    try:
        icon.run(setup=_setup)
    finally:
        hm.stop()
        _PID_PATH.unlink(missing_ok=True)
        _STATUS_PATH.unlink(missing_ok=True)
        _log.info("daemon stopped")
        _release_mutex(mutex_handle)


def stop_daemon() -> int:
    """Send a termination signal to the running daemon.

    Returns:
        0 on success, 1 if the daemon was not running or the PID file was
        missing or stale.
    """
    if not _PID_PATH.exists():
        print("press daemon: not running (no PID file)", file=sys.stderr)
        return 1

    try:
        pid = int(_PID_PATH.read_text(encoding="utf-8").strip())
    except ValueError:
        print("press daemon: error: invalid PID file", file=sys.stderr)
        return 1

    import psutil

    try:
        proc = psutil.Process(pid)
    except psutil.NoSuchProcess:
        print("press daemon: not running (stale PID file)", file=sys.stderr)
        _PID_PATH.unlink(missing_ok=True)
        return 1

    try:
        proc.terminate()
        proc.wait(timeout=5)
    except psutil.TimeoutExpired:
        proc.kill()

    _PID_PATH.unlink(missing_ok=True)
    print("press daemon: stopped")
    return 0


def daemon_status(*, as_json: bool = False) -> int:
    """Print the daemon's running status and return an exit code.

    Args:
        as_json: When ``True``, print a JSON object to stdout instead of plain text.

    Returns:
        0 if the daemon is running, 1 if not.
    """
    import contextlib

    pid: int | None = None
    if _PID_PATH.exists():
        with contextlib.suppress(ValueError):
            pid = int(_PID_PATH.read_text(encoding="utf-8").strip())

    running = False

    # On Windows: probe the mutex — most reliable indicator
    if sys.platform == "win32":
        probe = _acquire_mutex()
        if probe is None:
            running = True
        else:
            _release_mutex(probe)
    elif pid is not None:
        import psutil

        if psutil.pid_exists(pid):
            running = True
        else:
            _PID_PATH.unlink(missing_ok=True)

    if not as_json:
        if running:
            print(f"press daemon: running (pid={pid or '?'})")
        else:
            print("press daemon: not running")
        return 0 if running else 1

    # JSON output — merge live process data with persisted status file
    import json as _json

    status = _read_status_file() or {}
    uptime_seconds: int | None = None
    if running and "started_at" in status:
        from datetime import datetime

        with contextlib.suppress(ValueError, TypeError):
            started = datetime.fromisoformat(str(status["started_at"]))
            uptime_seconds = int((datetime.now(UTC) - started.astimezone(UTC)).total_seconds())

    result: dict[str, object] = {
        "running": running,
        "state": "running" if running else str(status.get("state", "stopped")),
        "pid": pid,
        "started_at": status.get("started_at"),
        "uptime_seconds": uptime_seconds,
        "version": status.get("version"),
        "restart_count": int(str(status.get("restart_count", 0))),
        "log_path": str(_LOG_PATH),
        "pid_file": str(_PID_PATH),
    }
    print(_json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if running else 1
