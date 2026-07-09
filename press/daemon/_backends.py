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

    def notify(self, message: str, title: str | None = None) -> None: ...

    def stop(self) -> None: ...


class KeyListener(Protocol):
    """Structural type for keyboard listeners (satisfied by pynput listeners)."""

    def start(self) -> None: ...

    def stop(self) -> None: ...


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


def create_key_listener(
    on_press: Callable[[Any], None],
    on_release: Callable[[Any], None],
) -> KeyListener:
    """Return a started-on-demand listener for raw key press/release events."""
    from pynput import keyboard as kb

    # pynput ships no type information; the cast is the seam's raison d'être.
    return cast("KeyListener", kb.Listener(on_press=on_press, on_release=on_release))


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
        setup: Called with the icon handle once the icon is visible.
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
    icon = pystray.Icon(name=name, icon=image, title=title, menu=menu)
    icon.run(setup=setup)
