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
       (``ha`` → halfwidth, ``html-e`` completes to html-escape).  An exact
       match that longer names still extend (``cr`` vs ``crlf``) is held
       *pending*: :meth:`confirm` or :meth:`on_timeout` commits it, while
       further typing continues toward the longer name.

    Every method returns a :data:`Resolution` — a work-queue item to emit, or
    ``None`` to keep listening:

    - ``("dispatch", command)`` — resolved, run *command*
    - ``("unknown_key", sequence)`` — the buffer can no longer match anything
    - ``("ambiguous", sequence)`` — committed (Enter/timeout) while several
      commands still extend the buffer
    - ``("timeout",)`` — cancelled with nothing typed, or by ``Esc``

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
        return self._unresolved()

    def on_timeout(self) -> Resolution:
        """Commit a pending exact match, or report why nothing was run."""
        if self._pending is not None:
            return ("dispatch", self._candidates[self._pending])
        return self._unresolved()

    def _unresolved(self) -> Resolution:
        """Classify a buffer that is being committed without a match.

        Nothing typed is a silent cancel (an accidental prefix press).  A
        buffer that several commands still extend (``ha`` → halfwidth / hash)
        is ``ambiguous`` rather than a plain timeout, so the user learns it was
        too short instead of seeing nothing happen.
        """
        buf = self._buffer
        if not buf:
            return ("timeout",)
        if any(name.startswith(buf) for name in self._candidates):
            return ("ambiguous", buf)
        return ("unknown_key", buf)

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


_DESCRIBE_LIMIT = 4  # commands listed in one notification before "+N more"


def describe_unresolved(buffer: str, candidates: Mapping[str, str]) -> str:
    """Explain, in one notification line, why *buffer* ran no command.

    For an ambiguous buffer each command it could still become is listed with
    how to reach it: the shortest continuation of what was typed, then the
    shortest sequence overall when that is different —
    ``ha → halfwidth (hal / hw), hash (has / hs)``.  A sequence that only an
    explicit commit resolves (``cr``, which ``crlf`` extends) is shown with
    ``+Enter``.  Only key sequences and command names appear — never anything
    from the clipboard.
    """
    targets = sorted({cmd for name, cmd in candidates.items() if name.startswith(buffer)})
    if not targets:
        return f"{buffer} → no command starts with this"
    parts = []
    for cmd in targets[:_DESCRIBE_LIMIT]:
        names = [name for name, target in candidates.items() if target == cmd]
        continuation = _shortest_trigger(
            [n for n in names if n.startswith(buffer)], cmd, candidates, len(buffer)
        )
        overall = _shortest_trigger(names, cmd, candidates, 0)
        ways = continuation if overall == continuation else f"{continuation} / {overall}"
        parts.append(f"{cmd} ({ways})")
    if len(targets) > _DESCRIBE_LIMIT:
        parts.append(f"… +{len(targets) - _DESCRIBE_LIMIT} more")
    return f"{buffer} → {', '.join(parts)}"


def _shortest_trigger(names: list[str], cmd: str, candidates: Mapping[str, str], start: int) -> str:
    """Return the shortest typed sequence among *names* that runs *cmd*.

    Mirrors :meth:`SequenceResolver._evaluate`: a prefix dispatches as soon as
    every candidate it reaches is *cmd*.  A name that never gets there by
    typing alone needs ``Enter`` and counts one key longer.  Prefixes shorter
    than *start* are skipped so a continuation never drops typed characters.
    """
    options = []
    for name in names:
        unique = next(
            (
                name[:k]
                for k in range(max(start, 1), len(name) + 1)
                if {t for n, t in candidates.items() if n.startswith(name[:k])} == {cmd}
            ),
            None,
        )
        options.append((len(unique), unique) if unique else (len(name) + 1, f"{name}+Enter"))
    return min(options)[1]


# Virtual-key codes of the modifier keys: the generic codes plus the left/right
# ones a low-level keyboard hook actually reports (VK_LSHIFT .. VK_RMENU).
MODIFIER_VKS = frozenset({0x10, 0x11, 0x12, 0x5B, 0x5C, 0xA0, 0xA1, 0xA2, 0xA3, 0xA4, 0xA5})


class KeySuppression:
    """Decide which raw key events the leader listener may swallow.

    A ``WH_KEYBOARD_LL`` hook runs *before* Windows updates the key's async
    state, so a swallowed key-up leaves the key logically held for the whole
    desktop.  The prefix chord is still down when the leader starts, and a
    blanket suppression used to eat its releases: Shift stayed "held" (clicks
    extended the text selection instead of clearing it) and pynput's
    ``GlobalHotKeys`` kept the chord in its pressed set, ignoring the next
    prefix press.

    The rule is therefore ownership: swallow only the presses the leader
    consumes and the releases matching them.  Modifiers are never swallowed —
    Shift is read for ``shift+<key>`` bindings but must still reach the OS.
    """

    def __init__(self) -> None:
        self._swallowed: set[int] = set()

    def reset(self) -> None:
        """Forget earlier presses; keys held into a new leader were pressed before it."""
        self._swallowed.clear()

    def should_suppress(self, vk: int, *, is_press: bool) -> bool:
        """Return ``True`` when the event for *vk* must not reach the OS."""
        if vk in MODIFIER_VKS:
            return False
        if is_press:
            self._swallowed.add(vk)
            return True
        try:
            self._swallowed.remove(vk)
        except KeyError:
            return False  # pressed before the leader started
        return True
