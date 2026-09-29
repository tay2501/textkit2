"""Third-party backend seam — the only module that imports pystray/pynput.

pystray has had no release since 2023 (0.19.5) and is a supply-chain risk;
pynput is maintained but shares the same exposure.  Every other daemon module
talks to these libraries exclusively through the wrappers and Protocols here,
so a backend swap (e.g. ctypes ``Shell_NotifyIcon`` / ``RegisterHotKey``)
touches this file only.

Imports stay inside functions so that CLI-only installs (no ``daemon`` extra)
can import the daemon package for status/log commands.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, cast

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    from PIL.Image import Image


class TrayIcon(Protocol):
    """Structural type for the system-tray icon handle (satisfied by pystray.Icon)."""

    icon: Any
    visible: bool

    def notify(self, message: str, title: str | None = None) -> None: ...

    def stop(self) -> None: ...


class KeyListener(Protocol):
    """Structural type for keyboard listeners (satisfied by pynput listeners).

    ``join`` is part of the seam because ``stop()`` is only a request: pynput
    listeners are threads, and the OS hook stays installed until the thread
    actually exits.  Callers that must not race the hook wait on it.
    """

    def start(self) -> None: ...

    def stop(self) -> None: ...

    def join(self, timeout: float | None = None) -> None: ...


# ---------------------------------------------------------------------------
# Keyboard backend (pynput)
# ---------------------------------------------------------------------------


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


def is_shift_key(key: object) -> bool:
    """Return ``True`` when *key* is any Shift variant."""
    from pynput import keyboard as kb

    return key in (kb.Key.shift, kb.Key.shift_l, kb.Key.shift_r)


_WM_KEYDOWN = 0x0100
_WM_SYSKEYDOWN = 0x0104


def create_leader_listener(
    on_press: Callable[[Any], None],
    on_release: Callable[[Any], None],
    should_suppress: Callable[..., bool],
) -> KeyListener:
    """Return a listener that swallows only the events *should_suppress* claims.

    pynput's ``suppress=True`` swallows *every* event, including the key-ups
    of the prefix chord the user is still holding — which leaves those keys
    logically down for the whole desktop.  pynput's documented alternative is
    a ``win32_event_filter`` that calls ``listener.suppress_event()`` for the
    events to hide (https://pynput.readthedocs.io/en/latest/faq.html).

    A suppressed event never reaches pynput's callbacks, so the filter itself
    delivers every event to *on_press* / *on_release* (as pynput key objects)
    and returns ``False`` so pynput does not deliver it a second time.  It runs
    on the hook thread, inside ``LowLevelHooksTimeout`` — the callbacks must
    stay cheap (they only feed the resolver and enqueue).

    Args:
        on_press: Called with the pressed key.
        on_release: Called with the released key.
        should_suppress: ``(vk, *, is_press) -> bool``; see
            :class:`press.daemon._sequence.KeySuppression`.
    """
    from pynput import keyboard as kb

    from press.keystrokes import vk_to_char

    special_keys = {key.value.vk: key for key in kb.Key}
    listener: Any = None

    def to_key(vk: int) -> object:
        try:
            return special_keys[vk]
        except KeyError:
            char = vk_to_char(vk)
            return kb.KeyCode.from_char(char) if char else kb.KeyCode.from_vk(vk)

    def event_filter(msg: int, data: Any) -> bool:
        vk = int(data.vkCode)
        is_press = msg in (_WM_KEYDOWN, _WM_SYSKEYDOWN)
        (on_press if is_press else on_release)(to_key(vk))
        if should_suppress(vk, is_press=is_press):
            listener.suppress_event()  # raises; pynput turns it into "swallow"
        return False  # already delivered above

    listener = kb.Listener(win32_event_filter=event_filter)
    # pynput ships no type information; the cast is the seam's raison d'être.
    return cast("KeyListener", listener)


def create_global_hotkeys(hotkeys: Mapping[str, Callable[[], None]]) -> KeyListener:
    """Return a global-hotkey listener mapping pynput specs to callbacks."""
    from pynput import keyboard as kb

    return cast("KeyListener", kb.GlobalHotKeys(dict(hotkeys)))


# ---------------------------------------------------------------------------
# Tray backend (pystray)
# ---------------------------------------------------------------------------


def run_tray_icon(
    *,
    name: str,
    title: str,
    image: Image,
    setup: Callable[[TrayIcon], None],
    on_quit: Callable[[], None],
) -> None:
    """Build the tray icon with the standard press menu and run it (blocking).

    Args:
        name: Icon identifier.
        title: Tooltip text.
        image: Initial icon image.
        setup: Called with the icon handle once the icon has been made
            visible (this wrapper sets ``visible`` — see pystray's contract).
        on_quit: Called when the user picks Quit, before the icon stops.
    """
    import pystray

    def _handle_quit(icon: pystray.Icon, _item: pystray.MenuItem) -> None:
        on_quit()
        icon.stop()

    menu = pystray.Menu(
        pystray.MenuItem("press daemon", None, enabled=False),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Quit", _handle_quit),
    )

    def _show_then_setup(icon: TrayIcon) -> None:
        # pystray's Icon.run(): "If you specify a custom setup function, you
        # must explicitly set this attribute."  Without it the Win32 backend
        # never sends NIM_ADD, so the icon, its Quit menu and every
        # notification (NIM_MODIFY) silently do not exist.
        icon.visible = True
        setup(icon)

    icon = pystray.Icon(name=name, icon=image, title=title, menu=menu)
    icon.run(setup=_show_then_setup)
