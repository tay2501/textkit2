"""Tests for press._version — the canonical package-version lookup."""

from __future__ import annotations

import importlib.metadata
from typing import TYPE_CHECKING

from press._version import press_version

if TYPE_CHECKING:
    import pytest


class TestPressVersion:
    """press_version() absorbs every failure mode of a damaged install."""

    def test_returns_the_installed_version(self) -> None:
        assert press_version() == importlib.metadata.version("press")

    def test_missing_distribution_returns_unknown(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def _raise(_name: str) -> str:
            raise importlib.metadata.PackageNotFoundError(_name)

        monkeypatch.setattr(importlib.metadata, "version", _raise)
        assert press_version() == "unknown"

    def test_missing_metadata_file_returns_unknown_on_python_313_314(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A dist-info folder with no METADATA yields ``None`` before 3.15."""
        monkeypatch.setattr(importlib.metadata, "version", lambda _name: None)
        assert press_version() == "unknown"

    def test_missing_metadata_file_returns_unknown_on_python_315(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """From 3.15 the same folder raises MetadataNotFound (a FileNotFoundError).

        Caught as OSError so the assertion holds on every supported
        interpreter, including the ones where the exception does not exist.
        """

        def _raise(_name: str) -> str:
            raise FileNotFoundError("METADATA")

        monkeypatch.setattr(importlib.metadata, "version", _raise)
        assert press_version() == "unknown"

    def test_empty_version_string_returns_unknown(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(importlib.metadata, "version", lambda _name: "")
        assert press_version() == "unknown"
