"""press daemon — system-tray icon + global-hotkey listener (Windows only).

This package is imported lazily: only when ``press daemon <action>`` is
invoked.  All third-party imports (pystray, pynput, Pillow, psutil) live
inside functions/methods so that CLI-only usage works without the ``daemon``
extra, and pystray/pynput are confined to :mod:`press.daemon._backends`.

Module layout::

    _backends.py   pystray/pynput seam (the only importers of those libraries)
    _tray.py       tray icon image generation (Pillow)
    _hotkeys.py    prefix hotkey, leader-key state machine, worker thread
    _dispatch.py   CommandDispatcher — clipboard transforms
    _lifecycle.py  singleton mutex, PID/status files, stop/status commands
    _logs.py       rotating log setup and the ``daemon logs`` command
    _service.py    run_daemon — wires everything together

The four public functions below are the daemon's entire external surface,
consumed by :mod:`press._cli_daemon`.
"""

from __future__ import annotations

from press.daemon._dispatch import CommandDispatcher
from press.daemon._hotkeys import HotkeyManager, LeaderKeyListener
from press.daemon._lifecycle import daemon_status, stop_daemon
from press.daemon._logs import daemon_logs
from press.daemon._service import run_daemon

__all__ = [
    "CommandDispatcher",
    "HotkeyManager",
    "LeaderKeyListener",
    "daemon_logs",
    "daemon_status",
    "run_daemon",
    "stop_daemon",
]
