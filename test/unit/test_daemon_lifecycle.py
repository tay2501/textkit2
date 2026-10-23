"""Tests for the daemon lifecycle commands: run / start / stop / restart.

``start`` spawns ``press daemon run`` in the background and returns once the
daemon is up; ``stop`` and ``start`` are idempotent like ``systemctl``.
"""

from __future__ import annotations

import subprocess
import sys
import threading
import time
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import psutil
import pytest

if TYPE_CHECKING:
    from pathlib import Path

_LC = "press.daemon._lifecycle"


@pytest.fixture
def pid_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "press.pid"
    monkeypatch.setattr(f"{_LC}._PID_PATH", path)
    return path


def _probe(monkeypatch: pytest.MonkeyPatch, *results: bool) -> list[int | None]:
    """Stub the running-daemon probe with *results*, recording each call's pid."""
    calls: list[int | None] = []
    answers = iter(results)

    def _fake(pid: int | None) -> bool:
        calls.append(pid)
        return next(answers)

    monkeypatch.setattr(f"{_LC}._probe_running", _fake)
    return calls


# ---------------------------------------------------------------------------
# Singleton mutex
# ---------------------------------------------------------------------------


@pytest.mark.windows_only
class TestMutexHandover:
    """A probe briefly owning the mutex must not make a starting daemon give up."""

    def test_waits_for_a_probe_to_release(self) -> None:
        from press.daemon._lifecycle import _acquire_mutex, _release_mutex

        probe = _acquire_mutex()
        assert probe is not None
        result: list[int | None] = []
        waiter = threading.Thread(target=lambda: result.append(_acquire_mutex(timeout_ms=5000)))
        waiter.start()
        time.sleep(0.2)  # the waiter is now blocked on the probe's ownership
        _release_mutex(probe)
        waiter.join(10)

        assert result and result[0] is not None
        # Ownership belongs to the waiter's (finished) thread: closing is enough.
        _release_mutex(result[0])

    @pytest.mark.usefixtures("held_daemon_mutex")
    def test_does_not_steal_from_a_live_owner(self) -> None:
        from press.daemon._lifecycle import _acquire_mutex

        assert _acquire_mutex(timeout_ms=100) is None


# ---------------------------------------------------------------------------
# stop
# ---------------------------------------------------------------------------


class TestStopDaemon:
    def test_not_running_is_success(
        self, pid_file: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _probe(monkeypatch, False)
        from press.daemon import stop_daemon

        assert stop_daemon() == 0
        assert "not running" in capsys.readouterr().out

    def test_invalid_pid_file_without_a_daemon_is_success(
        self, pid_file: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        pid_file.write_text("not-a-number", encoding="utf-8")
        calls = _probe(monkeypatch, False)
        from press.daemon import stop_daemon

        assert stop_daemon() == 0
        assert calls == [None]

    def test_running_without_pid_file_is_an_error(
        self, pid_file: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A daemon between taking the mutex and writing its PID cannot be stopped yet."""
        _probe(monkeypatch, True)
        from press.daemon import stop_daemon

        assert stop_daemon() == 1
        assert "try again" in capsys.readouterr().err

    def test_success_terminates_and_removes_pid_file(
        self, pid_file: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        pid_file.write_text("12345", encoding="utf-8")
        _probe(monkeypatch, True)
        proc = MagicMock()
        proc.name.return_value = "python.exe"
        with patch("psutil.Process", return_value=proc):
            from press.daemon import stop_daemon

            assert stop_daemon() == 0
        proc.terminate.assert_called_once()
        assert not pid_file.exists()
        assert "stopped" in capsys.readouterr().out

    def test_gone_pid_is_not_terminated(
        self, pid_file: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        pid_file.write_text("12345", encoding="utf-8")
        _probe(monkeypatch, True)
        with patch("psutil.Process", side_effect=psutil.NoSuchProcess(12345)):
            from press.daemon import stop_daemon

            assert stop_daemon() == 1

    def test_recycled_pid_is_not_terminated(
        self, pid_file: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A stale PID file may point at an unrelated process after PID reuse."""
        pid_file.write_text("12345", encoding="utf-8")
        _probe(monkeypatch, True)
        proc = MagicMock()
        proc.name.return_value = "notepad.exe"
        with patch("psutil.Process", return_value=proc):
            from press.daemon import stop_daemon

            assert stop_daemon() == 1
        proc.terminate.assert_not_called()
        proc.kill.assert_not_called()

    def test_access_denied_is_an_error(
        self, pid_file: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        pid_file.write_text("12345", encoding="utf-8")
        _probe(monkeypatch, True)
        proc = MagicMock()
        proc.name.return_value = "python.exe"
        proc.terminate.side_effect = psutil.AccessDenied(12345)
        with patch("psutil.Process", return_value=proc):
            from press.daemon import stop_daemon

            assert stop_daemon() == 1
        assert "could not stop" in capsys.readouterr().err
        assert pid_file.exists()

    def test_exit_during_terminate_is_success(
        self, pid_file: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        pid_file.write_text("12345", encoding="utf-8")
        _probe(monkeypatch, True)
        proc = MagicMock()
        proc.name.return_value = "python.exe"
        proc.terminate.side_effect = psutil.NoSuchProcess(12345)
        with patch("psutil.Process", return_value=proc):
            from press.daemon import stop_daemon

            assert stop_daemon() == 0

    def test_timeout_kills_and_waits_again(
        self, pid_file: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        pid_file.write_text("12345", encoding="utf-8")
        _probe(monkeypatch, True)
        proc = MagicMock()
        proc.name.return_value = "python.exe"
        proc.wait.side_effect = [psutil.TimeoutExpired(5), 0]
        with patch("psutil.Process", return_value=proc):
            from press.daemon import stop_daemon

            assert stop_daemon() == 0
        proc.kill.assert_called_once()
        assert proc.wait.call_count == 2
        assert not pid_file.exists()

    def test_survives_kill_is_an_error(
        self, pid_file: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        pid_file.write_text("12345", encoding="utf-8")
        _probe(monkeypatch, True)
        proc = MagicMock()
        proc.name.return_value = "python.exe"
        proc.wait.side_effect = psutil.TimeoutExpired(5)
        with patch("psutil.Process", return_value=proc):
            from press.daemon import stop_daemon

            assert stop_daemon() == 1


@pytest.mark.windows_only
class TestStopDaemonWindows:
    """The real mutex decides whether a daemon is there."""

    def test_stale_pid_file_is_removed_and_success(self, pid_file: Path) -> None:
        pid_file.write_text("99999", encoding="utf-8")
        from press.daemon import stop_daemon

        assert stop_daemon() == 0
        assert not pid_file.exists()

    @pytest.mark.usefixtures("held_daemon_mutex")
    def test_held_mutex_without_pid_file_is_an_error(self, pid_file: Path) -> None:
        from press.daemon import stop_daemon

        assert stop_daemon() == 1


# ---------------------------------------------------------------------------
# start
# ---------------------------------------------------------------------------


class TestDaemonArgv:
    def test_source_install_runs_the_module_without_cwd_on_sys_path(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # -P: a press/ folder in the current directory must never be imported
        # instead of the installed package.
        monkeypatch.delattr(sys, "frozen", raising=False)
        from press.daemon._lifecycle import _daemon_argv

        assert _daemon_argv() == [sys.executable, "-P", "-m", "press", "daemon", "run"]

    def test_frozen_build_runs_itself(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        from press.daemon._lifecycle import _daemon_argv

        assert _daemon_argv() == [sys.executable, "daemon", "run"]


@pytest.mark.windows_only
class TestSpawnDaemon:
    @pytest.fixture
    def home(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
        monkeypatch.setattr(f"{_LC}.press_dir", lambda: tmp_path)
        monkeypatch.setattr(f"{_LC}._STDERR_LOG_PATH", tmp_path / "daemon-stderr.log")
        return tmp_path

    def test_hidden_console_new_group_and_fixed_cwd(self, home: Path) -> None:
        with patch("subprocess.Popen") as popen:
            from press.daemon._lifecycle import _daemon_argv, _spawn_daemon

            _spawn_daemon()

        args, kwargs = popen.call_args
        assert args[0] == _daemon_argv()
        flags = kwargs["creationflags"]
        # DETACHED_PROCESS would give the interpreter behind a venv/uv
        # launcher a new, visible console window.
        assert not flags & subprocess.DETACHED_PROCESS
        assert flags & subprocess.CREATE_NO_WINDOW
        assert flags & subprocess.CREATE_NEW_PROCESS_GROUP
        assert flags & subprocess.CREATE_BREAKAWAY_FROM_JOB
        assert kwargs["cwd"] == home
        assert kwargs["stdin"] == subprocess.DEVNULL
        assert kwargs["stdout"] == subprocess.DEVNULL
        assert kwargs["stderr"].name == str(home / "daemon-stderr.log")

    def test_refused_breakaway_retries_inside_the_job(self, home: Path) -> None:
        denied = OSError(None, "Access is denied", None, 5)
        with patch("subprocess.Popen", side_effect=[denied, MagicMock()]) as popen:
            from press.daemon._lifecycle import _spawn_daemon

            _spawn_daemon()

        retry_flags = popen.call_args_list[1].kwargs["creationflags"]
        assert not retry_flags & subprocess.CREATE_BREAKAWAY_FROM_JOB
        assert retry_flags & subprocess.CREATE_NO_WINDOW

    def test_other_errors_are_not_retried(self, home: Path) -> None:
        missing = OSError(None, "The system cannot find the file specified", None, 2)
        with patch("subprocess.Popen", side_effect=missing) as popen:
            from press.daemon._lifecycle import _spawn_daemon

            with pytest.raises(OSError):
                _spawn_daemon()
        assert popen.call_count == 1


class TestStartDaemon:
    @pytest.fixture
    def env(
        self, pid_file: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> dict[str, object]:
        monkeypatch.setattr("sys.platform", "win32")
        stderr_log = tmp_path / "daemon-stderr.log"
        monkeypatch.setattr(f"{_LC}._STDERR_LOG_PATH", stderr_log)
        monkeypatch.setattr(f"{_LC}._missing_daemon_modules", list)
        monkeypatch.setattr("time.sleep", lambda _s: None)
        child = MagicMock(pid=500)
        child.poll.return_value = None
        state: dict[str, object] = {"child": child}

        def _spawn() -> MagicMock:
            state["spawned"] = True
            if "writes_pid" in state:
                pid_file.write_text(str(state["writes_pid"]), encoding="utf-8")
            return child

        monkeypatch.setattr(f"{_LC}._spawn_daemon", _spawn)
        return state

    @staticmethod
    def _daemon_proc(ppid: int) -> MagicMock:
        proc = MagicMock()
        proc.ppid.return_value = ppid
        return proc

    def test_not_windows_is_an_error(
        self, env: dict[str, object], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("sys.platform", "linux")
        from press.daemon import start_daemon

        assert start_daemon() == 1
        assert "spawned" not in env

    def test_already_running_is_success_without_spawning(
        self,
        env: dict[str, object],
        pid_file: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        pid_file.write_text("777", encoding="utf-8")
        _probe(monkeypatch, True)
        from press.daemon import start_daemon

        assert start_daemon() == 0
        assert "already running (pid=777)" in capsys.readouterr().out
        assert "spawned" not in env

    def test_missing_extra_is_reported_before_spawning(
        self,
        env: dict[str, object],
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        _probe(monkeypatch, False)
        monkeypatch.setattr(f"{_LC}._missing_daemon_modules", lambda: ["pystray"])
        from press.daemon import start_daemon

        assert start_daemon() == 1
        err = capsys.readouterr().err
        assert "pystray" in err
        assert "[daemon]" in err
        assert "spawned" not in env

    def test_spawn_failure_is_an_error(
        self, env: dict[str, object], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _probe(monkeypatch, False)
        monkeypatch.setattr(f"{_LC}._spawn_daemon", MagicMock(side_effect=OSError("nope")))
        from press.daemon import start_daemon

        assert start_daemon() == 1

    def test_ready_when_the_childs_interpreter_writes_its_pid(
        self,
        env: dict[str, object],
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        # venv/uv: the spawned python.exe is a launcher; the daemon is its child.
        env["writes_pid"] = 4242
        _probe(monkeypatch, False)
        with patch("psutil.Process", return_value=self._daemon_proc(ppid=500)):
            from press.daemon import start_daemon

            assert start_daemon() == 0
        assert "started (pid=4242)" in capsys.readouterr().out

    def test_ready_when_the_child_itself_writes_its_pid(
        self, env: dict[str, object], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        env["writes_pid"] = 500  # frozen build: no launcher in between
        _probe(monkeypatch, False)
        with patch("psutil.Process", return_value=self._daemon_proc(ppid=1)):
            from press.daemon import start_daemon

            assert start_daemon() == 0

    def test_unchanged_pid_file_is_not_readiness(
        self,
        env: dict[str, object],
        pid_file: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A stale PID file that could not be removed must not read as "started"."""
        pid_file.write_text("500", encoding="utf-8")
        _probe(monkeypatch, False, False)
        child = env["child"]
        assert isinstance(child, MagicMock)
        child.poll.return_value = 1
        with patch("psutil.Process", return_value=self._daemon_proc(ppid=1)):
            from press.daemon import start_daemon

            assert start_daemon() == 1

    def test_pid_of_an_unrelated_process_is_not_readiness(
        self, env: dict[str, object], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        env["writes_pid"] = 4242
        _probe(monkeypatch, False)
        monkeypatch.setattr(f"{_LC}._START_TIMEOUT", 0.0)
        with patch("psutil.Process", return_value=self._daemon_proc(ppid=9999)):
            from press.daemon import start_daemon

            assert start_daemon() == 1

    def test_child_exit_reports_its_stderr(
        self,
        env: dict[str, object],
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        _probe(monkeypatch, False, False)
        child = env["child"]
        assert isinstance(child, MagicMock)
        child.poll.return_value = 1
        (tmp_path / "daemon-stderr.log").write_text(
            "Traceback (most recent call last):\nImportError: no pystray\n", encoding="utf-8"
        )
        from press.daemon import start_daemon

        assert start_daemon() == 1
        err = capsys.readouterr().err
        assert "exit code 1" in err
        assert "ImportError: no pystray" in err

    def test_losing_a_concurrent_start_is_success(
        self,
        env: dict[str, object],
        pid_file: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Two starts at once: the child that lost the mutex exits; the other daemon runs."""
        _probe(monkeypatch, False, True)
        child = env["child"]
        assert isinstance(child, MagicMock)
        child.poll.return_value = 1
        from press.daemon import start_daemon

        assert start_daemon() == 0
        assert "already running" in capsys.readouterr().out

    def test_timeout_is_an_error(
        self,
        env: dict[str, object],
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        _probe(monkeypatch, False)
        monkeypatch.setattr(f"{_LC}._START_TIMEOUT", 0.0)
        from press.daemon import start_daemon

        assert start_daemon() == 1
        err = capsys.readouterr().err
        assert "still starting" in err
        assert "press daemon logs" in err


# ---------------------------------------------------------------------------
# run_daemon readiness
# ---------------------------------------------------------------------------


@pytest.mark.windows_only
class TestRunDaemonReadiness:
    """The PID file is the readiness signal: written only once the tray is up."""

    def test_pid_file_appears_only_after_setup(
        self, pid_file: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import os

        import press.daemon._service as service

        mutex_waits: list[int] = []

        def _acquire(timeout_ms: int = 0) -> int:
            mutex_waits.append(timeout_ms)
            return 42

        monkeypatch.setattr(f"{_LC}._acquire_mutex", _acquire)
        monkeypatch.setattr(f"{_LC}._release_mutex", lambda _h: None)
        monkeypatch.setattr(f"{_LC}._STATUS_PATH", tmp_path / "status.json")
        monkeypatch.setattr("press.daemon._logs._setup_logging", lambda: None)
        monkeypatch.setattr("press.config.load_config", MagicMock())
        for name in ("CommandDispatcher", "HotkeyManager", "_WorkerThread"):
            monkeypatch.setattr(service, name, MagicMock())
        monkeypatch.setattr(service, "_start_pipe_server", lambda _d: None)
        monkeypatch.setattr(service, "_create_tray_image", MagicMock())
        monkeypatch.setattr("press.commands.hotkey_sequence_candidates", lambda _p: {})

        seen: dict[str, bool] = {}

        def _tray(**kwargs: object) -> None:
            seen["before_setup"] = pid_file.exists()
            setup = kwargs["setup"]
            assert callable(setup)
            setup(MagicMock())
            seen["after_setup"] = pid_file.read_text(encoding="utf-8") == str(os.getpid())

        monkeypatch.setattr("press.daemon._backends.run_tray_icon", _tray)

        service.run_daemon()

        assert seen == {"before_setup": False, "after_setup": True}
        # A status/stop probe holds the mutex for microseconds; the daemon
        # waits for it instead of reporting "another instance".
        assert mutex_waits and mutex_waits[0] > 0


# ---------------------------------------------------------------------------
# CLI wiring
# ---------------------------------------------------------------------------


class TestDaemonCli:
    @staticmethod
    def _run(*argv: str) -> int:
        from press.__main__ import make_parser

        args = make_parser().parse_args(["daemon", *argv])
        result = args.func(args)
        assert isinstance(result, int)
        return result

    def test_run_is_the_foreground_daemon(self) -> None:
        with patch("press.daemon.run_daemon") as run:
            assert self._run("run") == 0
        run.assert_called_once_with()

    def test_start_returns_the_background_start_result(self) -> None:
        with (
            patch("press.daemon.start_daemon", return_value=0) as start,
            patch("press.daemon.run_daemon") as run,
        ):
            assert self._run("start") == 0
        start.assert_called_once_with()
        run.assert_not_called()

    def test_restart_stops_then_starts(self) -> None:
        order: list[str] = []
        with (
            patch("press.daemon.stop_daemon", side_effect=lambda: order.append("stop") or 0),
            patch("press.daemon.start_daemon", side_effect=lambda: order.append("start") or 0),
        ):
            assert self._run("restart") == 0
        assert order == ["stop", "start"]

    def test_restart_aborts_when_stop_fails(self) -> None:
        with (
            patch("press.daemon.stop_daemon", return_value=1),
            patch("press.daemon.start_daemon") as start,
        ):
            assert self._run("restart") == 1
        start.assert_not_called()
