"""Global hotkey listeners, the leader-key state machine, and the worker thread."""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING, override

from press.daemon._backends import (
    KeyListener,
    _normalize_key,
    create_global_hotkeys,
    create_key_listener,
    is_shift_key,
)

if TYPE_CHECKING:
    import queue

    from press.config import HotkeysConfig
    from press.daemon._dispatch import CommandDispatcher

_LEADER_TIMEOUT = 2.0  # seconds to wait for a binding key after prefix

# Token set for _to_pynput_hotkey: these need angle-bracket wrapping
_MODIFIER_TOKENS = frozenset({"ctrl", "shift", "alt", "cmd", "win", "meta"})


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
        self._listener: KeyListener | None = None
        self._shift_held = False
        self._done = threading.Event()

    def start(self) -> None:
        """Begin listening for the next meaningful keypress."""
        self._done.clear()
        self._shift_held = False

        self._listener = create_key_listener(self._on_press, self._on_release)
        self._listener.start()

        watcher = threading.Thread(target=self._timeout_watcher, daemon=True)
        watcher.start()

    def _timeout_watcher(self) -> None:
        self._done.wait(timeout=self._timeout)
        if not self._done.is_set():
            self._queue.put(("timeout",))
            self._stop()

    def _on_press(self, key: object) -> None:
        # Track shift state without treating it as a binding key
        if is_shift_key(key):
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
        if is_shift_key(key):
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
        self._hotkey_listener: KeyListener | None = None
        self._leader: LeaderKeyListener | None = None
        self._leader_active = False
        self._lock = threading.Lock()

    def start(self) -> None:
        """Start the GlobalHotKeys listener in a background daemon thread."""
        self._leader = LeaderKeyListener(self._config.bindings, self._queue)
        pynput_key = _to_pynput_hotkey(self._config.prefix)
        self._hotkey_listener = create_global_hotkeys({pynput_key: self._on_prefix})
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
