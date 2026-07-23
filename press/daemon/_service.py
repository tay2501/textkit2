"""Daemon entry point — wires the tray icon, hotkeys, and worker thread together."""

from __future__ import annotations

import os
import queue
import sys
from datetime import UTC
from typing import TYPE_CHECKING

from press.daemon import _lifecycle, _logs
from press.daemon._dispatch import CommandDispatcher
from press.daemon._hotkeys import HotkeyManager, _WorkerThread
from press.daemon._tray import _create_tray_image

if TYPE_CHECKING:
    from pathlib import Path

    from press.daemon._backends import TrayIcon
    from press.daemon._pipe import PipeServer


def run_daemon(config_path: Path | None = None) -> None:
    """Start the press daemon (blocking until quit from the tray menu).

    Args:
        config_path: Optional explicit path to the config TOML.  Defaults to
            ``%APPDATA%\\press\\config.toml``.

    Raises:
        SystemExit(1): On non-Windows or when another instance is already
            running.
    """
    if sys.platform != "win32":
        print("press daemon: error: only supported on Windows", file=sys.stderr)
        sys.exit(1)

    from press.config import load_config
    from press.daemon._backends import run_tray_icon

    _logs._setup_logging()

    config = load_config(config_path)

    mutex_handle = _lifecycle._acquire_mutex()
    if mutex_handle is None:
        print(
            "press daemon: error: another instance is already running",
            file=sys.stderr,
        )
        sys.exit(1)

    from datetime import datetime

    pid_path = _lifecycle._PID_PATH
    pid_path.parent.mkdir(parents=True, exist_ok=True)
    pid_path.write_text(str(os.getpid()), encoding="utf-8")

    import contextlib
    from importlib.metadata import version as _pkg_version

    _ver = "unknown"
    with contextlib.suppress(Exception):
        _ver = _pkg_version("press")

    _lifecycle._write_status_file(
        {
            "pid": os.getpid(),
            "started_at": datetime.now(UTC).astimezone().isoformat(timespec="seconds"),
            "version": _ver,
            "restart_count": 0,
            "state": "running",
        }
    )
    _logs._log.info("daemon started pid=%d version=%s", os.getpid(), _ver)

    work_queue: queue.Queue[tuple[str, ...]] = queue.Queue()
    dispatcher = CommandDispatcher(config)
    from press.commands import hotkey_sequence_candidates

    hm = HotkeyManager(
        config.hotkeys,
        work_queue,
        candidates=hotkey_sequence_candidates(config.pipelines),
    )
    worker = _WorkerThread(work_queue, dispatcher, hm)
    pipe_server = _start_pipe_server(dispatcher)

    def _setup(icon: TrayIcon) -> None:
        dispatcher.set_icon(icon)
        hm.start()
        worker.start()
        if config.ui.startup_notification:
            icon.notify("press daemon started", "press")

    def _on_quit() -> None:
        hm.stop()
        work_queue.put(("stop",))
        pid_path.unlink(missing_ok=True)

    try:
        run_tray_icon(
            name="press",
            title="press",
            image=_create_tray_image(),
            setup=_setup,
            on_quit=_on_quit,
        )
    finally:
        hm.stop()
        if pipe_server is not None:
            pipe_server.stop()
        pid_path.unlink(missing_ok=True)
        _lifecycle._STATUS_PATH.unlink(missing_ok=True)
        _logs._log.info("daemon stopped")
        _lifecycle._release_mutex(mutex_handle)


def _start_pipe_server(dispatcher: CommandDispatcher) -> PipeServer | None:
    """Start the named-pipe transform server, or return ``None`` on failure.

    Hotkeys are the daemon's primary interface and the CLI falls back to
    in-process transforms, so a pipe failure must never stop the daemon.
    """
    from press.daemon._pipe import PipeServer

    try:
        server = PipeServer(dispatcher)
        server.start()
    except OSError as exc:
        _logs._log.warning("pipe server not started: %s", exc)
        return None
    _logs._log.info("pipe server listening")
    return server
