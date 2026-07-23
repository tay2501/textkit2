"""Pure leader-key sequence resolution — no threads, no pynput, no clipboard.

:class:`SequenceResolver` owns the *rules* for turning the keys typed after the
prefix chord into a command; :mod:`press.daemon._hotkeys` owns the OS listener,
the threads, and the timeout that drive it.  Keeping the rules pure is what lets
them be tested as a plain table of (keystrokes → outcome) without standing up a
queue, a watcher thread, or a pynput mock.

Only the standard library is imported here — the pystray/pynput seam stays
confined to :mod:`press.daemon._backends`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping

# A work-queue item to emit, or ``None`` meaning "keep listening".
type Resolution = tuple[str, ...] | None


class SequenceResolver:
    """Resolve typed characters into a command, one keystroke at a time.

    Two-stage resolution:

    1. **First key**: a user ``[hotkeys.bindings]`` entry (``"w"``,
       ``"shift+u"``) dispatches immediately — personal shortcuts keep working
       and stay faster than typing a name.
    2. **Sequence**: otherwise printable keys accumulate into a buffer matched
       against *candidates* — the same names and aliases the CLI accepts
       (``press tm`` ⇔ prefix + ``t m``).  The buffer dispatches the moment
       every candidate still reachable from it resolves to the same command
       (``ha`` → halfwidth, ``html-e`` completes to html-encode).  An exact
       match that longer names still extend (``cr`` vs ``crlf``) is held
       *pending*: :meth:`confirm` or :meth:`on_timeout` commits it, while
       further typing continues toward the longer name.

    Every method returns a :data:`Resolution` — a work-queue item to emit, or
    ``None`` to keep listening:

    - ``("dispatch", command)`` — resolved, run *command*
    - ``("unknown_key", sequence)`` — the buffer can no longer match anything
    - ``("timeout",)`` — cancelled

    Args:
        candidates: Typeable sequence → dispatchable command, from
            :func:`press.commands.hotkey_sequence_candidates`.
        bindings: First-key specs (``"w"``, ``"shift+u"``) → command name,
            checked before sequence accumulation.
    """

    def __init__(self, candidates: Mapping[str, str], bindings: Mapping[str, str]) -> None:
        self._candidates = candidates
        self._bindings = bindings
        self._buffer = ""
        self._pending: str | None = None

    def reset(self) -> None:
        """Clear the buffer so the resolver can serve the next prefix press."""
        self._buffer = ""
        self._pending = None

    @property
    def buffer(self) -> str:
        """The characters typed so far (diagnostics and tests)."""
        return self._buffer

    def press(self, char: str, *, shift: bool = False) -> Resolution:
        """Feed one normalized key name; *char* is never a bare modifier.

        ``esc`` cancels, ``backspace`` edits the buffer, and ``enter`` commits
        (see :meth:`confirm`).
        """
        match char:
            case "esc":
                return ("timeout",)  # silent cancel
            case "backspace":
                self._buffer = self._buffer[:-1]
                # Never dispatch on an exact match here: the user is editing,
                # and deleting into a unique prefix must not fire a command.
                return self._evaluate(dispatch_exact=False)
            case "enter":
                return self.confirm()

        # First key only: user bindings win, so shift+<key> chords and personal
        # single-key shortcuts stay one keystroke.
        if not self._buffer:
            binding_key = f"shift+{char}" if shift else char
            if binding_key in self._bindings:
                return ("dispatch", self._bindings[binding_key])

        if len(char) != 1:  # f10, tab, … — never part of a typed name
            return ("unknown_key", char)

        self._buffer += char
        return self._evaluate(dispatch_exact=True)

    # ``_pending`` is the whole story for both committing methods: _evaluate
    # sets it whenever the buffer is an exact candidate it did not dispatch, so
    # "pending is None" and "the buffer matches nothing" are the same state.
    # They differ only in what an unresolved buffer means to the caller.

    def confirm(self) -> Resolution:
        """Commit the buffer as typed (the Enter key)."""
        if self._pending is not None:
            return ("dispatch", self._candidates[self._pending])
        return ("unknown_key", self._buffer)

    def on_timeout(self) -> Resolution:
        """Commit a pending exact match, or report the inactivity timeout."""
        if self._pending is not None:
            return ("dispatch", self._candidates[self._pending])
        return ("timeout",)

    def _evaluate(self, *, dispatch_exact: bool) -> Resolution:
        """Resolve the current buffer against the candidate names."""
        self._pending = None
        buf = self._buffer
        if not buf:
            return None
        targets = {cmd for name, cmd in self._candidates.items() if name.startswith(buf)}
        if not targets:
            return ("unknown_key", buf)
        if len(targets) == 1 and dispatch_exact:
            return ("dispatch", next(iter(targets)))
        if buf in self._candidates:
            self._pending = buf
        return None
