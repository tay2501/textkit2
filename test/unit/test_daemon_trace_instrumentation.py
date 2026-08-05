"""Tests confirming the `timed()`/`refresh_level()` instrumentation added for
the diagnostic trace feature wraps the intended call sites, without changing
observable dispatch behaviour.

`TestTimedFieldsWhitelist` at the bottom is the source-level counterpart: it
scans every `timed()` call in `press/` so a *future* call site cannot leak
clipboard body text into the plaintext daemon log."""

from __future__ import annotations

import ast
import contextlib
from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

if TYPE_CHECKING:
    import pytest


def _fake_timed(calls: list[tuple[str, dict[str, object]]]) -> Any:
    @contextlib.contextmanager
    def _timed(label: str, **fields: object) -> Any:
        calls.append((label, fields))
        yield

    return _timed


# ---------------------------------------------------------------------------
# CommandDispatcher.dispatch() — refresh_level() + clipboard.get/set
# ---------------------------------------------------------------------------


class TestDispatchRefreshLevel:
    def test_dispatch_calls_refresh_level(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from press.config import PressConfig
        from press.daemon import CommandDispatcher

        refreshed = []
        monkeypatch.setattr("press.daemon._logs.refresh_level", lambda: refreshed.append(True))
        with (
            patch("press.clipboard.get_clipboard_text", return_value="x"),
            patch("press.clipboard.set_clipboard_text"),
        ):
            CommandDispatcher(PressConfig()).dispatch("halfwidth")

        assert refreshed == [True]

    def test_dispatch_clear_also_refreshes_level(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """clear/hold/undo/type never call transform() — dispatch() must still refresh."""
        from press.config import PressConfig
        from press.daemon import CommandDispatcher

        refreshed = []
        monkeypatch.setattr("press.daemon._logs.refresh_level", lambda: refreshed.append(True))
        with (
            patch("press.clipboard.clear_clipboard"),
            patch("press.clipboard.get_clipboard_text", return_value="x"),
        ):
            CommandDispatcher(PressConfig()).dispatch("clear")

        assert refreshed == [True]


class TestDispatchClipboardTimed:
    def test_wraps_clipboard_get_and_set(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from press.config import PressConfig
        from press.daemon import CommandDispatcher

        calls: list[tuple[str, dict[str, object]]] = []
        monkeypatch.setattr("press.daemon._logs.timed", _fake_timed(calls))
        with (
            patch("press.clipboard.get_clipboard_text", return_value="ＡＢＣ"),
            patch("press.clipboard.set_clipboard_text") as mock_set,
        ):
            CommandDispatcher(PressConfig()).dispatch("halfwidth")

        labels = [label for label, _ in calls]
        assert "clipboard.get" in labels
        assert "clipboard.set" in labels
        mock_set.assert_called_once_with("ABC")

    def test_no_clipboard_body_text_in_fields(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Only counts/command names may appear in timed() fields — never clipboard text."""
        from press.config import PressConfig
        from press.daemon import CommandDispatcher

        calls: list[tuple[str, dict[str, object]]] = []
        monkeypatch.setattr("press.daemon._logs.timed", _fake_timed(calls))
        secret = "super-secret-clipboard-body"
        with (
            patch("press.clipboard.get_clipboard_text", return_value=secret),
            patch("press.clipboard.set_clipboard_text"),
        ):
            CommandDispatcher(PressConfig()).dispatch("halfwidth")

        for _label, fields in calls:
            assert secret not in repr(fields)


# ---------------------------------------------------------------------------
# CommandDispatcher.transform() — transform.run
# ---------------------------------------------------------------------------


class TestTransformTimed:
    def test_wraps_registry_command_with_cmd_and_chars(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from press.config import PressConfig
        from press.daemon import CommandDispatcher

        calls: list[tuple[str, dict[str, object]]] = []
        monkeypatch.setattr("press.daemon._logs.timed", _fake_timed(calls))

        d = CommandDispatcher(PressConfig())
        result = d.transform("halfwidth", "ＡＢＣ")

        assert result == "ABC"
        assert calls == [("transform.run", {"cmd": "halfwidth", "chars": 3})]

    def test_no_text_body_in_fields(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from press.config import PressConfig
        from press.daemon import CommandDispatcher

        calls: list[tuple[str, dict[str, object]]] = []
        monkeypatch.setattr("press.daemon._logs.timed", _fake_timed(calls))

        secret = "password-hunter2"
        CommandDispatcher(PressConfig()).transform("upper", secret)

        for _label, fields in calls:
            assert secret not in repr(fields)


# ---------------------------------------------------------------------------
# CommandDispatcher._type_clipboard() — keystrokes.type
# ---------------------------------------------------------------------------


class TestTypeClipboardTimed:
    def test_wraps_type_text_with_chars(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from press.config import PressConfig
        from press.daemon import CommandDispatcher

        calls: list[tuple[str, dict[str, object]]] = []
        monkeypatch.setattr("press.daemon._logs.timed", _fake_timed(calls))

        with (
            patch("press.clipboard.get_clipboard_text", return_value="abcde"),
            patch("press.keystrokes.type_text") as mock_type,
        ):
            CommandDispatcher(PressConfig()).dispatch("type")

        assert ("keystrokes.type", {"chars": 5}) in calls
        mock_type.assert_called_once()

    def test_no_text_body_in_fields(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from press.config import PressConfig
        from press.daemon import CommandDispatcher

        calls: list[tuple[str, dict[str, object]]] = []
        monkeypatch.setattr("press.daemon._logs.timed", _fake_timed(calls))

        secret = "keystrokes-secret-text"
        with (
            patch("press.clipboard.get_clipboard_text", return_value=secret),
            patch("press.keystrokes.type_text"),
        ):
            CommandDispatcher(PressConfig()).dispatch("type")

        for _label, fields in calls:
            assert secret not in repr(fields)


# ---------------------------------------------------------------------------
# HotkeyManager.reset_leader() — hotkey.wait_stopped
# ---------------------------------------------------------------------------


class TestResetLeaderTimed:
    def test_wraps_wait_stopped(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from press.config import HotkeysConfig
        from press.daemon._hotkeys import HotkeyManager

        calls: list[tuple[str, dict[str, object]]] = []
        monkeypatch.setattr("press.daemon._logs.timed", _fake_timed(calls))

        import queue

        hm = HotkeyManager(HotkeysConfig(), queue.Queue())
        mock_leader = MagicMock()
        hm._leader = mock_leader

        hm.reset_leader()

        mock_leader.wait_stopped.assert_called_once()
        assert calls == [("hotkey.wait_stopped", {})]

    def test_no_op_when_no_leader(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """No leader listener yet (daemon not fully started) — must not raise."""
        from press.config import HotkeysConfig
        from press.daemon._hotkeys import HotkeyManager

        calls: list[tuple[str, dict[str, object]]] = []
        monkeypatch.setattr("press.daemon._logs.timed", _fake_timed(calls))

        import queue

        hm = HotkeyManager(HotkeysConfig(), queue.Queue())
        hm.reset_leader()  # must not raise
        assert calls == []


# ---------------------------------------------------------------------------
# Source-level guard: timed() fields must never carry body text
# ---------------------------------------------------------------------------

#: Identifiers allowed as a ``timed()`` field value.  Deliberately tiny —
#: adding a name here is a reviewable act, which is the point.
_SAFE_IDENTIFIERS = frozenset({"cmd", "command"})


def _is_timed_call(node: ast.AST) -> bool:
    """Is *node* a call to ``timed(...)`` or ``_logs.timed(...)``?"""
    match node:
        case ast.Call(func=ast.Name(id="timed") | ast.Attribute(attr="timed")):
            return True
        case _:
            return False


def _is_safe_field(node: ast.expr) -> bool:
    """Is *node* an expression that provably cannot be clipboard body text?"""
    match node:
        case ast.Call(func=ast.Name(id="len")):  # chars=len(text)
            return True
        case ast.Constant(value=str() | int() | float()):  # mode="hotkey", count=0
            return True
        case ast.Name(id=name) if name in _SAFE_IDENTIFIERS:  # cmd=command
            return True
        case ast.Attribute(attr=attr) if attr in _SAFE_IDENTIFIERS:  # cmd=self.command
            return True
        case _:
            return False


class TestTimedFieldsWhitelist:
    """``daemon.log`` is plaintext, so a single ``timed("x", text=text)`` would
    persist clipboard bodies across 4 rotated files.  The classes above check
    the call sites that exist today; this one checks the ones nobody has
    written yet, the way ``TestImportBudget`` guards the import budget.

    See ``press.daemon._logs.timed``'s Security note and
    ``docs/dev/security-review-2026-08-06.md`` §4.
    """

    def test_all_timed_call_sites_pass_only_counts(self) -> None:
        import press

        checked: list[str] = []
        with_fields = 0
        for py in sorted(Path(press.__file__).parent.rglob("*.py")):
            tree = ast.parse(py.read_text(encoding="utf-8"), filename=str(py))
            for node in ast.walk(tree):
                if not _is_timed_call(node):
                    continue
                assert isinstance(node, ast.Call)  # narrowed by _is_timed_call
                checked.append(f"{py.name}:{node.lineno}")
                with_fields += bool(node.keywords)
                for kw in node.keywords:
                    assert _is_safe_field(kw.value), (
                        f"{py.name}:{node.lineno}: timed({kw.arg or '**'}=...) passes "
                        f"{ast.unparse(kw.value)!r}, which may be clipboard body text. "
                        "Only len(...), literals, and command names are allowed — "
                        "see press.daemon._logs.timed's Security note."
                    )

        # Fail loudly if the scan itself breaks rather than passing vacuously.
        assert len(checked) >= 10, f"expected the daemon's timed() call sites, found {checked}"
        assert with_fields >= 2, "transform.run and keystrokes.type carry fields"

    def test_guard_rejects_a_raw_text_field(self) -> None:
        """The guard must actually reject the mistake it exists to catch."""
        call = ast.parse('timed("clipboard.get", text=text)', mode="eval").body

        assert _is_timed_call(call)
        assert isinstance(call, ast.Call)
        assert not _is_safe_field(call.keywords[0].value)

    def test_guard_rejects_kwargs_splat(self) -> None:
        """``timed(label, **payload)`` hides its contents — must not pass."""
        call = ast.parse('timed("x", **payload)', mode="eval").body

        assert isinstance(call, ast.Call)
        assert call.keywords[0].arg is None  # a ** splat
        assert not _is_safe_field(call.keywords[0].value)
