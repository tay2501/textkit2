"""The single gate in front of every tray notification the daemon shows.

A notification is shown only when both agree:

- the user's switch (``press notify off`` / the ``notify-off`` hotkey,
  :mod:`press._notify`) is on, and
- Windows is not in a state where an application should stay quiet.

The second check follows Microsoft's guidance for notification-area balloons:
query ``SHQueryUserNotificationState`` before showing one.  It covers a
slideshow, a full-screen application, and Windows' presentation settings
automatically — but *not* sharing a window in Teams or Zoom, which is why the
explicit switch exists and is the one the user can rely on.
"""

from __future__ import annotations

import sys

from press._notify import notifications_enabled

# QUERY_USER_NOTIFICATION_STATE (shellapi.h) values in which an application
# should not show a notification.  QUNS_ACCEPTS_NOTIFICATIONS (5),
# QUNS_QUIET_TIME (6, the first hour after sign-in) and QUNS_APP (7) are left
# open: none of them means "someone else is watching this screen", and
# silencing quiet time would hide a mistyped hotkey for an hour after logon.
_BLOCKING_STATES = frozenset(
    {
        1,  # QUNS_NOT_PRESENT — screen saver, locked, fast user switching
        2,  # QUNS_BUSY — full-screen application or presentation settings
        3,  # QUNS_RUNNING_D3D_FULL_SCREEN
        4,  # QUNS_PRESENTATION_MODE
    }
)


def notifications_allowed() -> bool:
    """Return whether the daemon may show a tray notification right now."""
    return notifications_enabled() and windows_accepts_notifications()


def windows_accepts_notifications() -> bool:
    """Return ``False`` while Windows reports that notifications should wait.

    A failed query does not block: the explicit switch is the guarantee, and
    this check only saves the user from having to use it.
    """
    if sys.platform != "win32":
        return True
    state = _query_user_notification_state()
    return state is None or state not in _BLOCKING_STATES


def _query_user_notification_state() -> int | None:
    """Call ``SHQueryUserNotificationState``; ``None`` when it fails."""
    if sys.platform != "win32":
        raise OSError("SHQueryUserNotificationState is Windows-only")
    import ctypes

    shell32 = ctypes.WinDLL("shell32")
    state = ctypes.c_int()
    if shell32.SHQueryUserNotificationState(ctypes.byref(state)) != 0:  # S_OK
        return None
    return state.value
