"""Shared pytest fixtures and markers."""

import os
import sys
from collections.abc import Iterator

import pytest


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "windows_only: requires Windows (clipboard, hotkey, tray)")
    config.addinivalue_line("markers", "slow: slower integration/system tests")
    _isolate_daemon_names()


def _isolate_daemon_names() -> None:
    """Scope the daemon's per-user mutex and pipe names to this test process.

    Both derive from ``press._pipe.user_name()`` (``%USERNAME%``) and are
    machine-wide kernel objects, so ``%APPDATA%`` isolation does not separate
    them: with the developer's own daemon running, the mutex tests saw it as
    "held".  Set here, before collection, rather than in a fixture, so the
    module-level ``{**os.environ}`` copies test modules pass to subprocesses
    carry it too.
    """
    os.environ["USERNAME"] = f"press-test-{os.getpid()}"


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


@pytest.fixture
def held_daemon_mutex() -> Iterator[None]:
    """Hold the daemon singleton mutex from another thread, like a live daemon.

    A Win32 mutex is recursive for its owning thread, so acquiring it in the
    test's own thread would not look "held" to code running in that thread.
    """
    import threading

    from press.daemon._lifecycle import _acquire_mutex, _release_mutex

    acquired = threading.Event()
    done = threading.Event()
    handles: list[int | None] = []

    def _hold() -> None:
        handle = _acquire_mutex()
        handles.append(handle)
        acquired.set()
        done.wait(10)
        if handle is not None:
            _release_mutex(handle)

    holder = threading.Thread(target=_hold, daemon=True)
    holder.start()
    acquired.wait(10)
    assert handles[0] is not None, "the daemon mutex is already held"
    try:
        yield
    finally:
        done.set()
        holder.join(10)


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    skip_windows = pytest.mark.skip(reason="requires Windows")
    for item in items:
        if item.get_closest_marker("windows_only") and sys.platform != "win32":
            item.add_marker(skip_windows)
