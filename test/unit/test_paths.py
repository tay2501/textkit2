"""Unit tests for press._paths — shared filesystem locations."""

from __future__ import annotations

from pathlib import Path


class TestTracePath:
    def test_returns_path_instance(self) -> None:
        from press._paths import trace_path

        assert isinstance(trace_path(), Path)

    def test_filename_is_trace(self) -> None:
        from press._paths import trace_path

        assert trace_path().name == "trace"

    def test_parent_is_press_dir(self) -> None:
        from press._paths import press_dir, trace_path

        assert trace_path() == press_dir() / "trace"
