"""Tests for the daemon delegation protocol (press._pipe / press.daemon._pipe)."""

from __future__ import annotations

import json
import sys
from typing import Any
from unittest.mock import patch

import pytest


class TestProtocolEncoding:
    def test_request_round_trips_through_json(self) -> None:
        from press._pipe import PROTOCOL_VERSION, encode_request

        payload = json.loads(encode_request("trim", "  a  ", {"both": True}).decode("utf-8"))
        assert payload == {
            "v": PROTOCOL_VERSION,
            "cmd": "trim",
            "text": "  a  ",
            "kwargs": {"both": True},
        }

    def test_success_response_carries_text(self) -> None:
        from press._pipe import encode_response

        assert json.loads(encode_response(ok=True, text="ABC")) == {"ok": True, "text": "ABC"}

    def test_error_response_carries_message(self) -> None:
        from press._pipe import encode_response

        assert json.loads(encode_response(ok=False, error="boom")) == {
            "ok": False,
            "error": "boom",
        }

    def test_non_ascii_survives_encoding(self) -> None:
        from press._pipe import encode_request

        payload = json.loads(encode_request("halfwidth", "ＴＡＢＬＥ", {}).decode("utf-8"))
        assert payload["text"] == "ＴＡＢＬＥ"

    def test_pipe_name_is_per_user(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from press._pipe import pipe_name

        monkeypatch.setenv("USERNAME", "alice")
        assert pipe_name().endswith("-alice")
        monkeypatch.setenv("USERNAME", "bob")
        assert pipe_name().endswith("-bob")


class TestPidPathDuplication:
    """_pipe re-derives the PID path without pathlib; the two must not drift."""

    def test_matches_paths_module(self) -> None:
        from pathlib import Path

        from press._paths import press_dir
        from press._pipe import daemon_pid_path

        assert Path(daemon_pid_path()) == press_dir() / "press.pid"

    def test_matches_lifecycle_constant(self) -> None:
        from pathlib import Path

        from press._pipe import daemon_pid_path
        from press.daemon import _lifecycle

        assert Path(daemon_pid_path()) == _lifecycle._PID_PATH


class TestImportBudget:
    """Delegation must not slow down the machines it exists to speed up."""

    def test_module_body_avoids_heavy_imports(self) -> None:
        """ctypes/threading/pathlib cost file opens on every transform."""
        import subprocess
        import sys as _sys

        code = (
            "import sys; import press._pipe; "
            "print([m for m in ('ctypes', 'threading', 'pathlib') if m in sys.modules])"
        )
        out = subprocess.run(
            [_sys.executable, "-c", code], capture_output=True, text=True, check=True
        )
        assert out.stdout.strip() == "[]"


class _FakeDispatcher:
    """Stand-in for CommandDispatcher recording the kwargs it receives."""

    def __init__(self, result: str = "ok", error: Exception | None = None) -> None:
        self.result = result
        self.error = error
        self.calls: list[tuple[str, str, dict[str, Any] | None]] = []

    def transform(self, command: str, text: str, kwargs: dict[str, Any] | None = None) -> str:
        self.calls.append((command, text, kwargs))
        if self.error is not None:
            raise self.error
        return self.result


class TestHandleRequest:
    def _request(self, cmd: str, text: str = "x", kwargs: dict[str, Any] | None = None) -> bytes:
        from press._pipe import encode_request

        return encode_request(cmd, text, kwargs or {})

    def test_simple_command_dispatches_and_returns_text(self) -> None:
        from press.daemon._pipe import handle_request

        d = _FakeDispatcher(result="ABC")
        reply = json.loads(handle_request(d, self._request("halfwidth", "ＡＢＣ")))
        assert reply == {"ok": True, "text": "ABC"}
        assert d.calls == [("halfwidth", "ＡＢＣ", {})]

    def test_parametric_kwargs_are_forwarded(self) -> None:
        from press.daemon._pipe import handle_request

        d = _FakeDispatcher(result="a")
        handle_request(d, self._request("trim", "a  ", {"both": True}))
        assert d.calls[0][2] == {"both": True}

    def test_parametric_alias_resolves(self) -> None:
        from press.daemon._pipe import handle_request

        d = _FakeDispatcher(result="{}")
        reply = json.loads(handle_request(d, self._request("jf", "{}", {"indent": 4})))
        assert reply["ok"] is True

    def test_unknown_command_is_rejected(self) -> None:
        from press.daemon._pipe import handle_request

        d = _FakeDispatcher()
        reply = json.loads(handle_request(d, self._request("rm-rf")))
        assert reply["ok"] is False
        assert "unknown command" in reply["error"]
        assert d.calls == []

    def test_clipboard_commands_are_not_reachable(self) -> None:
        """hold/clear/dict must stay with the caller — never run in the daemon."""
        from press.daemon._pipe import handle_request

        d = _FakeDispatcher()
        for cmd in ("hold", "clear", "dict", "dict_reverse"):
            reply = json.loads(handle_request(d, self._request(cmd)))
            assert reply["ok"] is False, cmd
        assert d.calls == []

    def test_unexpected_kwargs_are_rejected(self) -> None:
        from press.daemon._pipe import handle_request

        d = _FakeDispatcher()
        reply = json.loads(handle_request(d, self._request("halfwidth", "x", {"evil": 1})))
        assert reply["ok"] is False
        assert "unexpected options" in reply["error"]
        assert d.calls == []

    def test_transform_error_becomes_error_response(self) -> None:
        from press.daemon._pipe import handle_request

        d = _FakeDispatcher(error=ValueError("bad json"))
        reply = json.loads(handle_request(d, self._request("json-format")))
        assert reply == {"ok": False, "error": "bad json"}

    def test_malformed_payload_is_rejected(self) -> None:
        from press.daemon._pipe import handle_request

        reply = json.loads(handle_request(_FakeDispatcher(), b"not json"))
        assert reply["ok"] is False
        assert "malformed request" in reply["error"]

    def test_wrong_protocol_version_is_rejected(self) -> None:
        from press.daemon._pipe import handle_request

        raw = json.dumps({"v": 99, "cmd": "halfwidth", "text": "x", "kwargs": {}}).encode()
        reply = json.loads(handle_request(_FakeDispatcher(), raw))
        assert reply["ok"] is False
        assert "unsupported protocol version" in reply["error"]

    def test_bad_text_type_is_rejected(self) -> None:
        from press.daemon._pipe import handle_request

        raw = json.dumps({"v": 1, "cmd": "halfwidth", "text": 42, "kwargs": {}}).encode()
        reply = json.loads(handle_request(_FakeDispatcher(), raw))
        assert reply["ok"] is False


@pytest.fixture
def daemon_present(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pretend a daemon is running (PID file present) and force the win32 path."""
    from press import _pipe

    monkeypatch.delenv("PRESS_NO_DAEMON", raising=False)
    monkeypatch.setattr(_pipe.sys, "platform", "win32")
    monkeypatch.setattr(_pipe, "_daemon_may_be_running", lambda: True)


@pytest.mark.usefixtures("daemon_present")
class TestTryDelegate:
    def test_returns_none_when_pipe_does_not_answer(self) -> None:
        from press import _pipe

        with patch.object(_pipe, "_round_trip_with_timeout", return_value=None):
            assert _pipe.try_delegate("halfwidth", "x", {}) is None

    def test_returns_daemon_text_on_success(self) -> None:
        from press import _pipe

        with patch.object(
            _pipe, "_round_trip_with_timeout", return_value=b'{"ok": true, "text": "ABC"}'
        ):
            assert _pipe.try_delegate("halfwidth", "ＡＢＣ", {}) == "ABC"

    def test_raises_on_daemon_reported_error(self) -> None:
        from press import _pipe

        with (
            patch.object(
                _pipe, "_round_trip_with_timeout", return_value=b'{"ok": false, "error": "boom"}'
            ),
            pytest.raises(_pipe.DaemonTransformError, match="boom"),
        ):
            _pipe.try_delegate("json-format", "{", {})

    def test_falls_back_on_unparseable_reply(self) -> None:
        from press import _pipe

        with patch.object(_pipe, "_round_trip_with_timeout", return_value=b"garbage"):
            assert _pipe.try_delegate("halfwidth", "x", {}) is None

    def test_env_var_disables_delegation(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from press import _pipe

        monkeypatch.setenv("PRESS_NO_DAEMON", "1")
        with patch.object(_pipe, "_round_trip_with_timeout") as rt:
            assert _pipe.try_delegate("halfwidth", "x", {}) is None
        rt.assert_not_called()

    def test_lone_surrogate_falls_back_instead_of_failing(self) -> None:
        """A lone surrogate survives a local transform but cannot be encoded."""
        from press import _pipe

        with patch.object(_pipe, "_round_trip_with_timeout") as rt:
            assert _pipe.try_delegate("halfwidth", "a\ud800b", {}) is None
        rt.assert_not_called()


class TestDelegationGate:
    def test_no_pid_file_skips_the_pipe_entirely(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Without a daemon, delegation must not even import ctypes."""
        from press import _pipe

        monkeypatch.setattr(_pipe.sys, "platform", "win32")
        monkeypatch.setattr(_pipe, "_daemon_may_be_running", lambda: False)
        with patch.object(_pipe, "_round_trip_with_timeout") as rt:
            assert _pipe.try_delegate("halfwidth", "x", {}) is None
        rt.assert_not_called()

    def test_gate_follows_the_pid_file(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Any
    ) -> None:
        from press import _pipe

        pid = tmp_path / "press.pid"
        monkeypatch.setattr(_pipe, "daemon_pid_path", lambda: str(pid))
        assert _pipe._daemon_may_be_running() is False
        pid.write_text("123")
        assert _pipe._daemon_may_be_running() is True

    @pytest.mark.skipif(sys.platform == "win32", reason="non-Windows behaviour")
    def test_non_windows_never_delegates(self) -> None:
        from press import _pipe

        assert _pipe.try_delegate("halfwidth", "x", {}) is None


def _run_cli(argv: list[str]) -> int:
    """Dispatch a CLI command through the real parser and return its exit code."""
    from press.__main__ import make_parser

    args = make_parser().parse_args(argv)
    return int(args.func(args))


class TestCliDelegation:
    """The CLI must produce identical output whether or not a daemon answers."""

    def test_transform_runs_locally_when_delegation_disabled(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.setenv("PRESS_NO_DAEMON", "1")
        assert _run_cli(["halfwidth", "ＴＡＢＬＥ１"]) == 0
        assert capsys.readouterr().out == "TABLE1"

    def test_transform_uses_daemon_result_when_available(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        with patch("press._pipe.try_delegate", return_value="FROM-DAEMON") as td:
            assert _run_cli(["halfwidth", "ＴＡＢＬＥ１"]) == 0
        assert td.call_args.args[0] == "halfwidth"
        assert capsys.readouterr().out == "FROM-DAEMON"

    def test_parametric_flags_are_sent_to_the_daemon(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """CLI flags must win over the daemon's config defaults."""
        with patch("press._pipe.try_delegate", return_value="a") as td:
            assert _run_cli(["trim", "--both", "  a  "]) == 0
        assert td.call_args.args[0] == "trim"
        assert td.call_args.args[2] == {"both": True}
        assert capsys.readouterr().out == "a"

    def test_daemon_error_is_reported_like_a_local_error(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from press._pipe import DaemonTransformError

        with patch("press._pipe.try_delegate", side_effect=DaemonTransformError("bad json")):
            assert _run_cli(["json-format", "{"]) == 1
        assert "press json-format: error: bad json" in capsys.readouterr().err

    def test_delegation_failure_falls_back_to_local_transform(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        with patch("press._pipe.try_delegate", return_value=None):
            assert _run_cli(["halfwidth", "ＴＡＢＬＥ１"]) == 0
        assert capsys.readouterr().out == "TABLE1"
