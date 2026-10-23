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


# A `status`/`stop` probe owns the singleton mutex for microseconds; waiting
# this long lets a daemon starting next to one take it over instead of
# reporting "another instance".
_MUTEX_WAIT_MS = 1000


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

    with _logs.timed("startup.config_load"):
        config = load_config(config_path)

    mutex_handle = _lifecycle._acquire_mutex(timeout_ms=_MUTEX_WAIT_MS)
    if mutex_handle is None:
        print(
            "press daemon: error: another instance is already running",
            file=sys.stderr,
        )
        sys.exit(1)

    from datetime import datetime

    pid_path = _lifecycle._PID_PATH

    from press._version import press_version

    _ver = press_version()

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

    with _logs.timed("startup.hotkeys_init"):
        hm = HotkeyManager(
            config.hotkeys,
            work_queue,
            candidates=hotkey_sequence_candidates(config.pipelines),
        )
    worker = _WorkerThread(work_queue, dispatcher, hm)
    with _logs.timed("startup.pipe_server_start"):
        pipe_server = _start_pipe_server(dispatcher)

    def _setup(icon: TrayIcon) -> None:
        dispatcher.set_icon(icon)
        hm.start()
        worker.start()
        # The PID file is the readiness signal `press daemon start` waits for,
        # so it appears only once the tray and hotkeys are up — never before
        # the pystray/pynput imports that fail without the daemon extra.
        pid_path.parent.mkdir(parents=True, exist_ok=True)
        pid_path.write_text(str(os.getpid()), encoding="utf-8")
        dispatcher.notify_startup()

    def _on_quit() -> None:
        hm.stop()
        work_queue.put(("stop",))
        pid_path.unlink(missing_ok=True)

    with _logs.timed("startup.tray_init"):
        tray_image = _create_tray_image()

    try:
        run_tray_icon(
            name="press",
            title="press",
            image=tray_image,
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
