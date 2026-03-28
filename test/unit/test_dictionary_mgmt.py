"""Tests for dictionary file management (press/dictionary.py)."""

import sys
from pathlib import Path

import pytest

from press.dictionary import add_entry, default_dict_path, list_entries, remove_entry


class TestDefaultDictPath:
    def test_returns_path_instance(self) -> None:
        result = default_dict_path()
        assert isinstance(result, Path)

    def test_filename_is_default_tsv(self) -> None:
        result = default_dict_path()
        assert result.name == "default.tsv"

    def test_parent_dir_is_dict(self) -> None:
        result = default_dict_path()
        assert result.parent.name == "dict"

    def test_windows_uses_appdata(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(sys, "platform", "win32")
        monkeypatch.setenv("APPDATA", "C:/Users/test/AppData/Roaming")
        result = default_dict_path()
        assert "press" in str(result)

    def test_non_windows_uses_config_home(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(sys, "platform", "linux")
        monkeypatch.delenv("APPDATA", raising=False)
        result = default_dict_path()
        assert "press" in str(result)


class TestListEntries:
    def test_basic_list(self, tmp_path: Path) -> None:
        tsv = tmp_path / "dict.tsv"
        tsv.write_text("a\t1\nb\t2\n", encoding="utf-8")
        result = list_entries(tsv)
        assert result == [("a", "1"), ("b", "2")]

    def test_ignores_comments_and_blanks(self, tmp_path: Path) -> None:
        tsv = tmp_path / "dict.tsv"
        tsv.write_text("# comment\na\t1\n\nb\t2\n", encoding="utf-8")
        result = list_entries(tsv)
        assert result == [("a", "1"), ("b", "2")]

    def test_empty_file_returns_empty_list(self, tmp_path: Path) -> None:
        tsv = tmp_path / "dict.tsv"
        tsv.write_text("", encoding="utf-8")
        result = list_entries(tsv)
        assert result == []

    def test_file_not_found_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            list_entries(tmp_path / "nonexistent.tsv")


class TestAddEntry:
    def test_add_to_new_file(self, tmp_path: Path) -> None:
        tsv = tmp_path / "sub" / "dict.tsv"
        add_entry("hello", "world", tsv)
        assert tsv.exists()
        content = tsv.read_text(encoding="utf-8")
        assert "hello\tworld\n" in content

    def test_add_to_existing_file(self, tmp_path: Path) -> None:
        tsv = tmp_path / "dict.tsv"
        tsv.write_text("a\t1\n", encoding="utf-8")
        add_entry("b", "2", tsv)
        content = tsv.read_text(encoding="utf-8")
        assert "a\t1\n" in content
        assert "b\t2\n" in content

    def test_creates_parent_dirs(self, tmp_path: Path) -> None:
        tsv = tmp_path / "deep" / "nested" / "dict.tsv"
        add_entry("key", "value", tsv)
        assert tsv.exists()

    def test_multiple_adds(self, tmp_path: Path) -> None:
        tsv = tmp_path / "dict.tsv"
        add_entry("a", "1", tsv)
        add_entry("b", "2", tsv)
        add_entry("c", "3", tsv)
        result = list_entries(tsv)
        assert result == [("a", "1"), ("b", "2"), ("c", "3")]


class TestRemoveEntry:
    def test_remove_existing_key(self, tmp_path: Path) -> None:
        tsv = tmp_path / "dict.tsv"
        tsv.write_text("a\t1\nb\t2\nc\t3\n", encoding="utf-8")
        result = remove_entry("b", tsv)
        assert result is True
        remaining = list_entries(tsv)
        assert ("b", "2") not in remaining
        assert ("a", "1") in remaining
        assert ("c", "3") in remaining

    def test_remove_nonexistent_key_returns_false(self, tmp_path: Path) -> None:
        tsv = tmp_path / "dict.tsv"
        tsv.write_text("a\t1\n", encoding="utf-8")
        result = remove_entry("z", tsv)
        assert result is False

    def test_remove_file_not_found_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            remove_entry("key", tmp_path / "nonexistent.tsv")

    def test_remove_preserves_comments(self, tmp_path: Path) -> None:
        tsv = tmp_path / "dict.tsv"
        tsv.write_text("# comment\na\t1\nb\t2\n", encoding="utf-8")
        remove_entry("a", tsv)
        content = tsv.read_text(encoding="utf-8")
        assert "# comment\n" in content
        assert "b\t2\n" in content
