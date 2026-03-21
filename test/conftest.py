"""Shared pytest fixtures and markers."""

import pytest


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "windows_only: requires Windows (clipboard, hotkey, tray)")
    config.addinivalue_line("markers", "slow: slower integration/system tests")
