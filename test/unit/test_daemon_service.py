"""Tests for press.daemon._service.run_daemon — startup-phase instrumentation."""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock

import pytest

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.windows_only
class TestRunDaemonStartupTimed:
    """run_daemon() wraps config load / tray init / hotkeys init / pipe server
    start with timed("startup.*") so a slow phase shows up in the trace log."""

    def test_startup_phases_are_timed(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from press.config import PressConfig

        calls: list[tuple[str, dict[str, Any]]] = []

        @contextlib.contextmanager
        def fake_timed(label: str, **fields: Any) -> Any:
            calls.append((label, fields))
            yield

        monkeypatch.setattr("sys.platform", "win32")
        monkeypatch.setattr("press.daemon._logs.timed", fake_timed)
        monkeypatch.setattr("press.daemon._logs._setup_logging", lambda: None)
        monkeypatch.setattr("press.config.load_config", lambda path=None: PressConfig())
        monkeypatch.setattr("press.daemon._lifecycle._acquire_mutex", lambda: 12345)
        monkeypatch.setattr("press.daemon._lifecycle._release_mutex", lambda handle: None)
        monkeypatch.setattr("press.daemon._lifecycle._write_status_file", lambda data: None)
        monkeypatch.setattr("press.daemon._lifecycle._PID_PATH", tmp_path / "press.pid")
        monkeypatch.setattr("press.daemon._lifecycle._STATUS_PATH", tmp_path / "status.json")
        monkeypatch.setattr("press.daemon._service._create_tray_image", lambda *a, **k: MagicMock())
        monkeypatch.setattr(
            "press.daemon._service.HotkeyManager", MagicMock(return_value=MagicMock())
        )
        monkeypatch.setattr(
            "press.daemon._service._WorkerThread", MagicMock(return_value=MagicMock())
        )
        monkeypatch.setattr(
            "press.daemon._service._start_pipe_server",
            lambda dispatcher: MagicMock(),
        )

        def fake_run_tray_icon(
            *, name: str, title: str, image: object, setup: Any, on_quit: Any
        ) -> None:
            setup(MagicMock())
            on_quit()

        monkeypatch.setattr("press.daemon._backends.run_tray_icon", fake_run_tray_icon)

        from press.daemon._service import run_daemon

        run_daemon()

        labels = [label for label, _ in calls]
        assert "startup.config_load" in labels
        assert "startup.tray_init" in labels
        assert "startup.hotkeys_init" in labels
        assert "startup.pipe_server_start" in labels


class TestRunTrayIconVisibility:
    """pystray's Icon.run() contract: a custom setup callback must set
    ``icon.visible = True`` itself, otherwise the icon is never added to the
    notification area (Win32 NIM_ADD) and notifications silently fail."""

    def test_icon_is_visible_before_caller_setup_runs(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import sys
        import types

        from press.daemon._backends import run_tray_icon

        visible_seen: list[bool] = []

        class FakeIcon:
            def __init__(self, **_kwargs: Any) -> None:
                self.visible = False

            def run(self, setup: Any) -> None:
                setup(self)  # pystray calls it once the loop is running

        fake = types.ModuleType("pystray")
        fake.Icon = FakeIcon  # type: ignore[attr-defined]
        fake.Menu = MagicMock()  # type: ignore[attr-defined]
        fake.MenuItem = MagicMock()  # type: ignore[attr-defined]
        monkeypatch.setitem(sys.modules, "pystray", fake)

        run_tray_icon(
            name="press",
            title="press",
            image=MagicMock(),
            setup=lambda icon: visible_seen.append(icon.visible),
            on_quit=lambda: None,
        )

        assert visible_seen == [True]
