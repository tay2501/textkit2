"""Tests for dictionary transform functions (F-08, F-09)."""

from pathlib import Path

import pytest

from press.transforms.dictionary import dict_forward, dict_reverse, load_tsv


class TestLoadTsv:
    def test_basic_load(self, tmp_path: Path) -> None:
        tsv = tmp_path / "dict.tsv"
        tsv.write_text("hello\tworld\n", encoding="utf-8")
        result = load_tsv(tsv)
        assert result == {"hello": "world"}

    def test_multiple_entries(self, tmp_path: Path) -> None:
        tsv = tmp_path / "dict.tsv"
        tsv.write_text("a\t1\nb\t2\nc\t3\n", encoding="utf-8")
        result = load_tsv(tsv)
        assert result == {"a": "1", "b": "2", "c": "3"}

    def test_ignores_comment_lines(self, tmp_path: Path) -> None:
        tsv = tmp_path / "dict.tsv"
        tsv.write_text("# this is a comment\nhello\tworld\n", encoding="utf-8")
        result = load_tsv(tsv)
        assert result == {"hello": "world"}

    def test_ignores_blank_lines(self, tmp_path: Path) -> None:
        tsv = tmp_path / "dict.tsv"
        tsv.write_text("a\t1\n\nb\t2\n", encoding="utf-8")
        result = load_tsv(tsv)
        assert result == {"a": "1", "b": "2"}

    def test_ignores_third_column(self, tmp_path: Path) -> None:
        tsv = tmp_path / "dict.tsv"
        tsv.write_text("key\tvalue\textra\tignored\n", encoding="utf-8")
        result = load_tsv(tsv)
        assert result == {"key": "value"}

    def test_empty_file_returns_empty_dict(self, tmp_path: Path) -> None:
        tsv = tmp_path / "dict.tsv"
        tsv.write_text("", encoding="utf-8")
        result = load_tsv(tsv)
        assert result == {}

    def test_file_not_found_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            load_tsv(tmp_path / "nonexistent.tsv")

    def test_accepts_str_path(self, tmp_path: Path) -> None:
        tsv = tmp_path / "dict.tsv"
        tsv.write_text("x\ty\n", encoding="utf-8")
        result = load_tsv(str(tsv))
        assert result == {"x": "y"}

    def test_utf8_japanese_entries(self, tmp_path: Path) -> None:
        tsv = tmp_path / "dict.tsv"
        tsv.write_text("猫\tcat\n犬\tdog\n", encoding="utf-8")
        result = load_tsv(tsv)
        assert result == {"猫": "cat", "犬": "dog"}


class TestDictForward:
    def test_single_line_match(self) -> None:
        table = {"hello": "world"}
        assert dict_forward("hello", table) == "world"

    def test_single_line_no_match(self) -> None:
        table = {"hello": "world"}
        assert dict_forward("goodbye", table) == "goodbye"

    def test_multiline_replaces_matched(self) -> None:
        table = {"apple": "fruit", "carrot": "vegetable"}
        text = "apple\ncarrot\nstone"
        result = dict_forward(text, table)
        assert result == "fruit\nvegetable\nstone"

    def test_multiline_preserves_unmatched(self) -> None:
        table = {"a": "1"}
        text = "a\nb\nc"
        result = dict_forward(text, table)
        assert result == "1\nb\nc"

    def test_strips_line_before_lookup(self) -> None:
        table = {"hello": "world"}
        assert dict_forward("  hello  ", table) == "world"

    def test_empty_table_returns_original(self) -> None:
        assert dict_forward("hello\nworld", {}) == "hello\nworld"

    def test_multiline_preserves_trailing_newline(self) -> None:
        table = {"a": "1"}
        result = dict_forward("a\nb\n", table)
        assert result == "1\nb\n"

    def test_empty_text_returns_empty(self) -> None:
        assert dict_forward("", {}) == ""


class TestDictReverse:
    def test_reverse_lookup(self) -> None:
        table = {"hello": "world"}
        assert dict_reverse("world", table) == "hello"

    def test_reverse_no_match(self) -> None:
        table = {"hello": "world"}
        assert dict_reverse("goodbye", table) == "goodbye"

    def test_reverse_multiline(self) -> None:
        table = {"apple": "fruit", "carrot": "vegetable"}
        text = "fruit\nvegetable\nstone"
        result = dict_reverse(text, table)
        assert result == "apple\ncarrot\nstone"

    def test_reverse_does_not_modify_original_table(self) -> None:
        table = {"a": "1", "b": "2"}
        original_keys = set(table.keys())
        dict_reverse("1\n2", table)
        assert set(table.keys()) == original_keys
