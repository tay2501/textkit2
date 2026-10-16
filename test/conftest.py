"""Shared pytest fixtures and markers."""

import sys

import pytest


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "windows_only: requires Windows (clipboard, hotkey, tray)")
    config.addinivalue_line("markers", "slow: slower integration/system tests")


@pytest.fixture
def notifications_open(
    tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Make the daemon's notification gate say yes on any machine.

    Tests that assert a tray notification would otherwise depend on the
    developer's ``press notify`` switch and on Windows' own notification state
    (a CI runner without an interactive desktop reports it cannot show any).
    """
    import press.daemon._notifications as gate

    marker = tmp_path_factory.mktemp("notify") / "notify-off"
    monkeypatch.setattr("press._paths.notify_off_path", lambda: marker)
    monkeypatch.setattr(gate, "windows_accepts_notifications", lambda: True)


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    skip_windows = pytest.mark.skip(reason="requires Windows")
    for item in items:
        if item.get_closest_marker("windows_only") and sys.platform != "win32":
            item.add_marker(skip_windows)
