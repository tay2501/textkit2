"""Global hotkey listeners, the leader-key state machine, and the worker thread."""

from __future__ import annotations

import threading
import time
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
    """Capture keys after the prefix until a command resolves.

    Two-stage resolution:

    1. **First key**: user ``[hotkeys.bindings]`` entries (``"w"``,
       ``"shift+u"``) dispatch immediately — personal shortcuts keep working.
    2. **Sequence**: otherwise printable keys accumulate into a buffer
       matched against *candidates* — the same command names and aliases the
       CLI accepts (``press tm`` ⇔ prefix + ``t m``).  The buffer dispatches
       the moment every candidate it can still reach resolves to the same
       command (``tm`` → trim, ``up`` → upper, ``html-e`` completes to
       html-encode).  When different commands remain reachable from an exact
       match (``cr`` vs ``crlf``), it is held *pending* — Enter or the
       inactivity timeout confirms it, further typing continues toward the
       longer name.

    Esc cancels, Backspace edits the buffer, and every keypress re-arms the
    inactivity timeout.  Results are enqueued:

    - ``("dispatch", command)`` — resolved, run *command*
    - ``("unknown_key", sequence)`` — the buffer matches nothing
    - ``("timeout",)`` — cancelled (Esc) or nothing resolvable was typed

    Args:
        bindings: Mapping of first-key specs (e.g. ``"w"``, ``"shift+u"``)
            to command names — checked before sequence accumulation.
        candidates: Mapping of typeable sequence → dispatchable command,
            from :func:`press.commands.hotkey_sequence_candidates`.
        work_queue: Queue shared with the worker thread.
        timeout: Seconds of inactivity before the pending match (or a
            timeout) is emitted.
    """

    def __init__(
        self,
        bindings: dict[str, str],
        candidates: dict[str, str],
        work_queue: queue.Queue[tuple[str, ...]],
        timeout: float = _LEADER_TIMEOUT,
    ) -> None:
        self._bindings = bindings
        self._candidates = candidates
        self._queue = work_queue
        self._timeout = timeout
        self._listener: KeyListener | None = None
        self._shift_held = False
        self._buffer = ""
        self._pending: str | None = None
        self._deadline = 0.0
        self._done = threading.Event()
        self._finish_lock = threading.Lock()

    def start(self) -> None:
        """Begin listening for the key sequence."""
        self._done.clear()
        self._shift_held = False
        self._buffer = ""
        self._pending = None
        self._deadline = time.monotonic() + self._timeout

        # suppress=True: sequence characters must not leak into the focused
        # window.  Bounded by the inactivity watcher below.
        self._listener = create_key_listener(self._on_press, self._on_release, suppress=True)
        self._listener.start()

        watcher = threading.Thread(target=self._timeout_watcher, daemon=True)
        watcher.start()

    def _timeout_watcher(self) -> None:
        while not self._done.wait(timeout=0.05):
            if time.monotonic() >= self._deadline:
                pending = self._pending
                if pending is not None:
                    self._finish(("dispatch", self._candidates[pending]))
                else:
                    self._finish(("timeout",))
                return

    def _finish(self, item: tuple[str, ...]) -> None:
        """Enqueue *item* exactly once and stop listening (thread-safe)."""
        with self._finish_lock:
            if self._done.is_set():
                return
            self._done.set()
        self._queue.put(item)
        self._stop()

    def _on_press(self, key: object) -> None:
        # Track shift state without treating it as a sequence key
        if is_shift_key(key):
            self._shift_held = True
            return

        # Ignore other standalone modifiers (ctrl, alt, …)
        char = _normalize_key(key)
        if char is None or char in {"ctrl", "alt", "cmd", "meta", "win"}:
            return

        self._deadline = time.monotonic() + self._timeout  # re-arm per key

        match char:
            case "esc":
                self._finish(("timeout",))  # silent cancel
                return
            case "backspace":
                self._buffer = self._buffer[:-1]
                self._evaluate(dispatch_exact=False)
                return
            case "enter":
                if self._pending is not None:
                    self._finish(("dispatch", self._candidates[self._pending]))
                elif self._buffer in self._candidates:
                    self._finish(("dispatch", self._candidates[self._buffer]))
                else:
                    self._finish(("unknown_key", self._buffer))
                return

        # First key: user bindings win (personal shortcuts, shift+ chords)
        if not self._buffer:
            binding_key = f"shift+{char}" if self._shift_held else char
            if binding_key in self._bindings:
                self._finish(("dispatch", self._bindings[binding_key]))
                return

        if len(char) != 1:  # f10, tab, … — never part of a typed name
            self._finish(("unknown_key", char))
            return

        self._buffer += char
        self._evaluate(dispatch_exact=True)

    def _evaluate(self, *, dispatch_exact: bool) -> None:
        """Resolve the current buffer against the candidate names.

        Fires as soon as every candidate still reachable from the buffer
        resolves to the same command (``up`` → upper instantly, ``html-e``
        completes to html-encode).  An exact match that different commands
        extend (``cr`` vs ``crlf``) is held pending for Enter / timeout.
        """
        buf = self._buffer
        self._pending = None
        if not buf:
            return
        targets = {cmd for name, cmd in self._candidates.items() if name.startswith(buf)}
        if not targets:
            self._finish(("unknown_key", buf))
            return
        if len(targets) == 1 and dispatch_exact:
            self._finish(("dispatch", next(iter(targets))))
            return
        if buf in self._candidates:
            self._pending = buf

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
        candidates: Sequence-name → command map for typed dispatch; defaults
            to the registry candidates without pipeline names.
    """

    def __init__(
        self,
        config: HotkeysConfig,
        work_queue: queue.Queue[tuple[str, ...]],
        candidates: dict[str, str] | None = None,
    ) -> None:
        if candidates is None:
            from press.commands import hotkey_sequence_candidates

            candidates = hotkey_sequence_candidates()
        self._config = config
        self._candidates = candidates
        self._queue = work_queue
        self._hotkey_listener: KeyListener | None = None
        self._leader: LeaderKeyListener | None = None
        self._leader_active = False
        self._lock = threading.Lock()

    def start(self) -> None:
        """Start the GlobalHotKeys listener in a background daemon thread."""
        self._leader = LeaderKeyListener(self._config.bindings, self._candidates, self._queue)
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
