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
from press.daemon._sequence import SequenceResolver

if TYPE_CHECKING:
    import queue

    from press.config import HotkeysConfig
    from press.daemon._dispatch import CommandDispatcher

_LEADER_TIMEOUT = 2.0  # seconds of inactivity before the sequence is committed
# Absolute cap on how long the suppressing listener may hold the keyboard,
# whatever the user types.  Unlike _LEADER_TIMEOUT this is never re-armed.
_LEADER_HARD_LIMIT = 10.0
# How long to wait for the suppressing hook thread to actually exit.  Bounded
# so a wedged pynput thread cannot stall the worker queue forever.
_STOP_TIMEOUT = 1.0

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
    """Drive a :class:`SequenceResolver` from the OS keyboard listener.

    This class owns only the machinery: the pynput listener, the shift-state
    tracking, the timeout watcher, and the once-only handoff to the work
    queue.  What a keystroke *means* lives in
    :class:`press.daemon._sequence.SequenceResolver`.

    While the listener runs it is created with ``suppress=True``, so typed
    sequence characters do not leak into the focused window.  That also means
    they are **consumed** — a mistyped sequence swallows those keystrokes
    instead of delivering them to the application.  Two independent bounds keep
    the suppression from outliving its purpose:

    - *timeout* seconds of inactivity, re-armed on every keypress; and
    - :data:`_LEADER_HARD_LIMIT` seconds in total, which cannot be re-armed.

    The hard limit is a safety valve rather than part of the interaction: it
    exists because this is the only place in press that takes input away from
    the whole desktop, so a bug in resolution must not be able to hold the
    keyboard indefinitely.  It abandons any pending match — releasing the
    keyboard matters more than running a command the user may have forgotten.

    Results are enqueued: ``("dispatch", command)``, ``("unknown_key",
    sequence)``, or ``("timeout",)``.

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
        self._resolver = SequenceResolver(candidates, bindings)
        self._queue = work_queue
        self._timeout = timeout
        self._listener: KeyListener | None = None
        # The listener that has been asked to stop but may not have exited yet.
        self._stopping: KeyListener | None = None
        self._shift_held = False
        self._deadline = 0.0
        self._hard_deadline = 0.0
        self._done = threading.Event()
        self._finish_lock = threading.Lock()

    def start(self) -> None:
        """Begin listening for the key sequence."""
        self._done.clear()
        self._shift_held = False
        self._resolver.reset()
        now = time.monotonic()
        self._deadline = now + self._timeout
        self._hard_deadline = now + _LEADER_HARD_LIMIT

        # suppress=True: sequence characters must not leak into the focused
        # window.  Bounded by the watcher below.
        self._listener = create_key_listener(self._on_press, self._on_release, suppress=True)
        self._listener.start()

        watcher = threading.Thread(target=self._timeout_watcher, daemon=True)
        watcher.start()

    def _timeout_watcher(self) -> None:
        """Release the keyboard once either deadline passes.

        Waits for the time actually remaining instead of polling, re-reading
        ``_deadline`` each round because :meth:`_on_press` pushes it back from
        the listener thread.
        """
        while True:
            remaining = min(self._deadline, self._hard_deadline) - time.monotonic()
            if remaining <= 0:
                break
            if self._done.wait(timeout=remaining):
                return  # resolved by a keypress
        if time.monotonic() >= self._hard_deadline:
            self._finish(("timeout",))  # safety valve: drop any pending match
        else:
            self._finish(self._resolver.on_timeout() or ("timeout",))

    def _finish(self, item: tuple[str, ...]) -> None:
        """Stop listening and enqueue *item* exactly once (thread-safe).

        The stop request comes *before* the enqueue so the consumer can never
        observe the item while ``_stopping`` is still unset — that ordering is
        what makes :meth:`wait_stopped` a reliable barrier.
        """
        with self._finish_lock:
            if self._done.is_set():
                return
            self._done.set()
        self._stop()
        self._queue.put(item)

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
        resolution = self._resolver.press(char, shift=self._shift_held)
        if resolution is not None:
            self._finish(resolution)

    def _on_release(self, key: object) -> None:
        if is_shift_key(key):
            self._shift_held = False

    def _stop(self) -> None:
        listener, self._listener = self._listener, None
        if listener is not None:
            listener.stop()
            self._stopping = listener

    def wait_stopped(self, timeout: float = _STOP_TIMEOUT) -> None:
        """Block until the suppressing hook thread has exited.

        Called from the worker thread — never from the hook thread itself,
        which would be joining itself.
        """
        listener, self._stopping = self._stopping, None
        if listener is not None:
            listener.join(timeout)


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
        """Re-arm the prefix hotkey once the leader listener has really stopped.

        Waiting matters for commands that synthesize input.  ``stop()`` only
        asks the pynput hook thread to quit; until it exits the low-level hook
        is still installed with suppression on, and Windows delivers injected
        events to a ``WH_KEYBOARD_LL`` hook like any other — so ``type`` would
        have its own keystrokes swallowed by press itself.
        """
        if self._leader is not None:
            self._leader.wait_stopped()
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
