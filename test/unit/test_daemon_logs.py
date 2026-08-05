"""Unit tests for press.daemon._logs — diagnostic trace level + timed() helper."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture(autouse=True)
def _isolated_log(monkeypatch: pytest.MonkeyPatch) -> logging.Logger:
    """Reset the module logger's level and handlers around each test.

    ``_log`` is a module-level singleton shared with the rest of the daemon,
    so tests must not leak level changes to each other.
    """
    from press.daemon import _logs

    original_level = _logs._log.level
    yield _logs._log
    _logs._log.setLevel(original_level)


class TestRefreshLevel:
    def test_sets_debug_when_marker_present(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from press.daemon import _logs

        marker = tmp_path / "trace"
        marker.touch()
        monkeypatch.setattr(_logs, "trace_path", lambda: marker)

        _logs.refresh_level()

        assert _logs._log.level == logging.DEBUG

    def test_sets_info_when_marker_absent(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from press.daemon import _logs

        marker = tmp_path / "trace"
        monkeypatch.setattr(_logs, "trace_path", lambda: marker)

        _logs.refresh_level()

        assert _logs._log.level == logging.INFO


class TestTimed:
    def test_emits_debug_record_when_enabled(self, caplog: pytest.LogCaptureFixture) -> None:
        from press.daemon._logs import _log, timed

        _log.setLevel(logging.DEBUG)
        with (
            caplog.at_level(logging.DEBUG, logger="press.daemon"),
            timed("transform.run", cmd="upper", chars=5),
        ):
            pass

        records = [r for r in caplog.records if r.name == "press.daemon"]
        assert len(records) == 1
        assert records[0].levelno == logging.DEBUG
        assert "transform.run" in records[0].message
        assert "elapsed_ms=" in records[0].message
        assert "cmd=upper" in records[0].message
        assert "chars=5" in records[0].message

    def test_no_record_when_disabled(self, caplog: pytest.LogCaptureFixture) -> None:
        from press.daemon._logs import _log, timed

        with caplog.at_level(logging.DEBUG, logger="press.daemon"):
            # Set the level *after* entering caplog.at_level, which would
            # otherwise force DEBUG for the duration of the context.
            _log.setLevel(logging.INFO)
            with timed("transform.run", cmd="upper", chars=5):
                pass

        records = [r for r in caplog.records if r.name == "press.daemon"]
        assert records == []

    def test_body_still_runs_when_disabled(self, caplog: pytest.LogCaptureFixture) -> None:
        from press.daemon._logs import _log, timed

        _log.setLevel(logging.INFO)
        ran = []
        with timed("transform.run"):
            ran.append(True)

        assert ran == [True]

    def test_exception_propagates_and_no_record_is_lost(self) -> None:
        from press.daemon._logs import _log, timed

        _log.setLevel(logging.DEBUG)
        with pytest.raises(ValueError, match="boom"), timed("transform.run"):
            raise ValueError("boom")
