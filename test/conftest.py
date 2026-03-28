"""Shared pytest fixtures and markers."""

import sys

import pytest


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "windows_only: requires Windows (clipboard, hotkey, tray)")
    config.addinivalue_line("markers", "slow: slower integration/system tests")


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    skip_windows = pytest.mark.skip(reason="requires Windows")
    for item in items:
        if item.get_closest_marker("windows_only") and sys.platform != "win32":
            item.add_marker(skip_windows)
