"""Keystroke synthesis via Win32 ``SendInput`` (Windows only).

The ``type`` command types the clipboard into the focused window one character
at a time instead of letting the application run its own paste handler.  That
matters when ``Ctrl+V`` stalls: a paste makes the *foreground* app read the
clipboard and parse whatever rich formats it finds, and a slow reader freezes
the window the user is looking at.  Typing moves the clipboard read into the
press daemon's worker thread and hands the target nothing but characters.

What it is **not** is a drop-in replacement for a paste.  Keystrokes go through
the application's input path, so this module is a keyboard, not a transport:

- Newlines are ``VK_RETURN`` presses by default (see :data:`NewlineMode`) —
  ``WM_CHAR 0x0A`` is ignored by most edit controls.  In a chat client Enter
  *sends the message*; ``newline = "unicode"`` or ``"skip"`` exist for that.
- Tabs are sent as Unicode ``0x09`` rather than ``VK_TAB`` on purpose: the
  virtual key moves focus between controls, the character inserts a tab.
- Delivery depends on the target calling ``TranslateMessage``, and UIPI blocks
  injection into windows running at a higher integrity level.

The character planning is a pure function (:func:`plan_keystrokes`) so the
rules are testable off-Windows; only :func:`type_text` touches ``user32``.
"""

from __future__ import annotations

import sys
from typing import Literal, NamedTuple

__all__ = [
    "DEFAULT_CHUNK_DELAY",
    "DEFAULT_CHUNK_SIZE",
    "DEFAULT_MAX_CHARS",
    "VK_RETURN",
    "KeyStroke",
    "NewlineMode",
    "plan_keystrokes",
    "type_text",
]

# How a newline in the clipboard is turned into input.
type NewlineMode = Literal["enter", "unicode", "skip"]

VK_RETURN = 0x0D

# Windows caps a thread's message queue at 10,000 posted messages
# (USERPostMessageLimit).  Every character costs at least a WM_KEYDOWN and a
# WM_KEYUP, so a long text sent in one burst can overrun a slow application's
# queue and lose characters *silently*.  Sending in chunks with a pause between
# them keeps the queue draining; the total cap is the backstop.
DEFAULT_MAX_CHARS = 2000
DEFAULT_CHUNK_SIZE = 200
DEFAULT_CHUNK_DELAY = 0.005  # seconds between chunks

# Modifiers that would change what the synthesized keys mean (Ctrl+Enter,
# Shift+Enter, Alt+<key>).  The prefix chord is Ctrl+Shift+<key>, so the user's
# fingers may still be on them when the command fires.
_MODIFIER_VKS = (0x10, 0x11, 0x12, 0x5B, 0x5C)  # SHIFT, CONTROL, MENU, LWIN, RWIN
_MODIFIER_TIMEOUT = 0.5  # seconds to wait for the user to let go


class KeyStroke(NamedTuple):
    """One key event pair (press + release) to synthesize.

    ``vk`` is a virtual-key code, or ``0`` to send ``unit`` as a Unicode
    packet; ``unit`` is the UTF-16 code unit used in that case and ignored
    otherwise.
    """

    vk: int
    unit: int


def _utf16_units(char: str) -> tuple[int, ...]:
    """Split *char* into the UTF-16 code units ``KEYEVENTF_UNICODE`` carries.

    ``wScan`` is a 16-bit field, so anything outside the BMP travels as its
    surrogate pair — two packets the receiving application reassembles.
    """
    code = ord(char)
    if code <= 0xFFFF:
        return (code,)
    code -= 0x10000
    return (0xD800 + (code >> 10), 0xDC00 + (code & 0x3FF))


def plan_keystrokes(text: str, *, newline: NewlineMode = "enter") -> list[KeyStroke]:
    """Turn *text* into the key events that reproduce it, in order.

    Line endings are normalized first (CRLF/CR/LF all become one newline) so a
    Windows clipboard does not type Enter twice per line.

    Args:
        text: The text to type.
        newline: What a newline becomes — ``"enter"`` a ``VK_RETURN`` press,
            ``"unicode"`` a literal ``U+000A`` character, ``"skip"`` nothing.
    """
    from press.transforms.lineending import to_lf

    strokes: list[KeyStroke] = []
    for char in to_lf(text):
        if char == "\n":
            match newline:
                case "enter":
                    strokes.append(KeyStroke(VK_RETURN, 0))
                case "unicode":
                    strokes.append(KeyStroke(0, 0x0A))
                case "skip":
                    continue
            continue
        strokes.extend(KeyStroke(0, unit) for unit in _utf16_units(char))
    return strokes


def type_text(
    text: str,
    *,
    newline: NewlineMode = "enter",
    max_chars: int = DEFAULT_MAX_CHARS,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_delay: float = DEFAULT_CHUNK_DELAY,
) -> int:
    """Type *text* into the focused window and return the characters sent.

    Args:
        text: The text to type.
        newline: See :func:`plan_keystrokes`.
        max_chars: Refuse texts longer than this.  Typing is not atomic — a
            long run is visible, interruptible, and can overrun the target's
            message queue — so the limit is a guard rail, not a formality.
        chunk_size: Key events per ``SendInput`` call.
        chunk_delay: Seconds to pause between chunks.

    Raises:
        ValueError: When *text* is longer than *max_chars*.
        RuntimeError: When a modifier key is still held after
            :data:`_MODIFIER_TIMEOUT`, or when ``SendInput`` is refused (UIPI:
            the focused window runs at a higher integrity level).
        OSError: On non-Windows platforms.
    """
    if len(text) > max_chars:
        raise ValueError(f"text is {len(text)} characters; the limit is {max_chars}")
    if not text:
        return 0
    if sys.platform == "win32":
        _win_send(plan_keystrokes(text, newline=newline), chunk_size, chunk_delay)
        return len(text)
    raise OSError("Keystroke synthesis is only supported on Windows")


# ---------------------------------------------------------------------------
# Windows implementation via ctypes
# ---------------------------------------------------------------------------

if sys.platform == "win32":
    import ctypes
    import ctypes.wintypes
    import time

    # use_last_error=True: ctypes may clobber the thread's error value before a
    # bare GetLastError() call returns it — same rule as clipboard.py / _pipe.py.
    _user32 = ctypes.WinDLL("user32", use_last_error=True)

    _INPUT_KEYBOARD = 1
    _KEYEVENTF_KEYUP = 0x0002
    _KEYEVENTF_UNICODE = 0x0004
    _KEY_DOWN_STATE = 0x8000  # high bit of GetAsyncKeyState

    class _MOUSEINPUT(ctypes.Structure):
        _fields_ = (
            ("dx", ctypes.wintypes.LONG),
            ("dy", ctypes.wintypes.LONG),
            ("mouseData", ctypes.wintypes.DWORD),
            ("dwFlags", ctypes.wintypes.DWORD),
            ("time", ctypes.wintypes.DWORD),
            ("dwExtraInfo", ctypes.c_size_t),  # ULONG_PTR
        )

    class _KEYBDINPUT(ctypes.Structure):
        _fields_ = (
            ("wVk", ctypes.wintypes.WORD),
            ("wScan", ctypes.wintypes.WORD),
            ("dwFlags", ctypes.wintypes.DWORD),
            ("time", ctypes.wintypes.DWORD),
            ("dwExtraInfo", ctypes.c_size_t),  # ULONG_PTR
        )

    class _HARDWAREINPUT(ctypes.Structure):
        _fields_ = (
            ("uMsg", ctypes.wintypes.DWORD),
            ("wParamL", ctypes.wintypes.WORD),
            ("wParamH", ctypes.wintypes.WORD),
        )

    class _INPUT_UNION(ctypes.Union):
        # All three arms are declared so ctypes derives the real union size;
        # MOUSEINPUT is the largest and hand-computed padding would be a
        # silent-corruption bug on the next architecture.
        _fields_ = (("mi", _MOUSEINPUT), ("ki", _KEYBDINPUT), ("hi", _HARDWAREINPUT))

    class _INPUT(ctypes.Structure):
        _anonymous_ = ("u",)
        _fields_ = (("type", ctypes.wintypes.DWORD), ("u", _INPUT_UNION))

    _user32.SendInput.argtypes = [
        ctypes.wintypes.UINT,
        ctypes.POINTER(_INPUT),
        ctypes.c_int,
    ]
    _user32.SendInput.restype = ctypes.wintypes.UINT
    _user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
    _user32.GetAsyncKeyState.restype = ctypes.c_short

    def _build_inputs(strokes: list[KeyStroke]) -> ctypes.Array[_INPUT]:
        """Build the ``INPUT`` array for *strokes* (two events per stroke)."""
        events = (_INPUT * (len(strokes) * 2))()
        for index, stroke in enumerate(strokes):
            flags = _KEYEVENTF_UNICODE if stroke.vk == 0 else 0
            for offset, extra in ((0, 0), (1, _KEYEVENTF_KEYUP)):
                event = events[index * 2 + offset]
                event.type = _INPUT_KEYBOARD
                event.ki = _KEYBDINPUT(
                    wVk=stroke.vk,
                    wScan=stroke.unit,
                    dwFlags=flags | extra,
                    time=0,
                    dwExtraInfo=0,
                )
        return events

    def _wait_modifiers_released(timeout: float = _MODIFIER_TIMEOUT) -> None:
        """Block until no modifier key is physically held.

        ``SendInput`` does not reset keyboard state, so a Ctrl still held from
        the prefix chord would turn the synthesized Enter into Ctrl+Enter.
        Refusing beats typing something the user did not ask for.

        Raises:
            RuntimeError: When a modifier is still down after *timeout*.
        """
        deadline = time.monotonic() + timeout
        while any(_user32.GetAsyncKeyState(vk) & _KEY_DOWN_STATE for vk in _MODIFIER_VKS):
            if time.monotonic() >= deadline:
                raise RuntimeError("modifier key still held — release Ctrl/Shift/Alt and retry")
            time.sleep(0.01)

    def _win_send(strokes: list[KeyStroke], chunk_size: int, chunk_delay: float) -> None:
        """Send *strokes* in chunks, verifying every event was accepted."""
        _wait_modifiers_released()
        for start in range(0, len(strokes), chunk_size):
            if start:
                time.sleep(chunk_delay)
            events = _build_inputs(strokes[start : start + chunk_size])
            sent = _user32.SendInput(len(events), events, ctypes.sizeof(_INPUT))
            if sent != len(events):
                raise RuntimeError(
                    f"SendInput accepted {sent}/{len(events)} events "
                    f"(error {ctypes.get_last_error()}) — the focused window may run elevated"
                )
