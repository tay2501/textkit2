"""Tests for the notification on/off switch and the daemon's single gate.

Every tray notification goes through
:func:`press.daemon._notifications.notifications_allowed`, which combines the
user's explicit switch (``press notify off`` / the ``notify-off`` hotkey) with
Windows' own "do not show notifications now" state.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

if TYPE_CHECKING:
    from pathlib import Path


class TestSwitch:
    def test_off_then_on(self, tmp_path: Path) -> None:
        from press._notify import notifications_enabled, set_notifications_enabled

        marker = tmp_path / "notify-off"
        with patch("press._paths.notify_off_path", return_value=marker):
            assert notifications_enabled() is True
            set_notifications_enabled(False)
            assert notifications_enabled() is False
            set_notifications_enabled(True)
            assert notifications_enabled() is True

    def test_each_direction_is_idempotent(self, tmp_path: Path) -> None:
        """Pressing "off" twice in a panic must not turn notifications back on."""
        from press._notify import notifications_enabled, set_notifications_enabled

        with patch("press._paths.notify_off_path", return_value=tmp_path / "notify-off"):
            set_notifications_enabled(False)
            set_notifications_enabled(False)
            assert notifications_enabled() is False
            set_notifications_enabled(True)
            set_notifications_enabled(True)
            assert notifications_enabled() is True


class TestGate:
    def test_switched_off_blocks_even_when_windows_accepts(self, tmp_path: Path) -> None:
        from press.daemon._notifications import notifications_allowed

        marker = tmp_path / "notify-off"
        marker.touch()
        with (
            patch("press._paths.notify_off_path", return_value=marker),
            patch("press.daemon._notifications.windows_accepts_notifications", return_value=True),
        ):
            assert notifications_allowed() is False

    def test_windows_busy_blocks(self, tmp_path: Path) -> None:
        from press.daemon._notifications import notifications_allowed

        with (
            patch("press._paths.notify_off_path", return_value=tmp_path / "notify-off"),
            patch("press.daemon._notifications.windows_accepts_notifications", return_value=False),
        ):
            assert notifications_allowed() is False

    def test_allowed_when_both_say_yes(self, tmp_path: Path) -> None:
        from press.daemon._notifications import notifications_allowed

        with (
            patch("press._paths.notify_off_path", return_value=tmp_path / "notify-off"),
            patch("press.daemon._notifications.windows_accepts_notifications", return_value=True),
        ):
            assert notifications_allowed() is True


class TestWindowsState:
    """QUERY_USER_NOTIFICATION_STATE values (shellapi.h) mapped to a yes/no."""

    @pytest.mark.parametrize(
        ("state", "accepts"),
        [
            (1, False),  # QUNS_NOT_PRESENT — screen saver, locked, fast user switching
            (2, False),  # QUNS_BUSY — full-screen app or presentation settings
            (3, False),  # QUNS_RUNNING_D3D_FULL_SCREEN
            (4, False),  # QUNS_PRESENTATION_MODE
            (5, True),  # QUNS_ACCEPTS_NOTIFICATIONS
            (6, True),  # QUNS_QUIET_TIME — first hour after sign-in; not a meeting
            (7, True),  # QUNS_APP — a Store app in the foreground; not a meeting
        ],
    )
    def test_state_mapping(self, state: int, accepts: bool) -> None:
        from press.daemon import _notifications

        with (
            patch.object(_notifications.sys, "platform", "win32"),
            patch.object(_notifications, "_query_user_notification_state", return_value=state),
        ):
            assert _notifications.windows_accepts_notifications() is accepts

    def test_failed_query_does_not_block(self) -> None:
        """The explicit switch is the guarantee; the Windows query only helps."""
        from press.daemon import _notifications

        with (
            patch.object(_notifications.sys, "platform", "win32"),
            patch.object(_notifications, "_query_user_notification_state", return_value=None),
        ):
            assert _notifications.windows_accepts_notifications() is True

    def test_non_windows_accepts(self) -> None:
        from press.daemon import _notifications

        with patch.object(_notifications.sys, "platform", "linux"):
            assert _notifications.windows_accepts_notifications() is True

    @pytest.mark.windows_only
    def test_real_query_returns_a_known_state(self) -> None:
        from press.daemon._notifications import _query_user_notification_state

        assert _query_user_notification_state() in {1, 2, 3, 4, 5, 6, 7}
