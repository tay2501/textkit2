"""The tray-notification on/off switch shared by the CLI and the daemon.

Deliberately two explicit states rather than a toggle: when a call turns into
a screen share, the user may hit "off" two or three times to be sure, and
every one of those must leave notifications off.  Persisted as a marker file
(:func:`press._paths.notify_off_path`) so ``press notify off`` reaches an
already-running daemon with no restart — the daemon reads it before every
notification (:mod:`press.daemon._notifications`).
"""

from __future__ import annotations

from press import _paths


def notifications_enabled() -> bool:
    """Return whether the user's switch allows tray notifications."""
    return not _paths.notify_off_path().exists()


def set_notifications_enabled(enabled: bool) -> None:
    """Turn tray notifications on or off; repeating either call is a no-op."""
    marker = _paths.notify_off_path()
    if enabled:
        marker.unlink(missing_ok=True)
    else:
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.touch()
