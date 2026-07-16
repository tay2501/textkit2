"""Tests for regex / fixed-string replacement."""

import pytest

from press.transforms.replace import regex_replace


class TestRegexReplace:
    def test_basic(self) -> None:
        assert regex_replace("foo bar foo", pattern="foo", repl="baz") == "baz bar baz"

    def test_regex_pattern(self) -> None:
        assert regex_replace("a1b22c333", pattern=r"\d+", repl="#") == "a#b#c#"

    def test_group_reference(self) -> None:
        result = regex_replace("2026-07-17", pattern=r"(\d+)-(\d+)-(\d+)", repl=r"\3/\2/\1")
        assert result == "17/07/2026"

    def test_delete_matches_by_default(self) -> None:
        assert regex_replace("a-b-c", pattern="-") == "abc"

    def test_empty_pattern_is_noop(self) -> None:
        assert regex_replace("unchanged", repl="X") == "unchanged"

    def test_ignore_case(self) -> None:
        assert regex_replace("Foo FOO foo", pattern="foo", repl="x", ignore_case=True) == "x x x"

    def test_case_sensitive_by_default(self) -> None:
        assert regex_replace("Foo foo", pattern="foo", repl="x") == "Foo x"

    def test_fixed_literal_metacharacters(self) -> None:
        assert regex_replace("1.5 + 2.5", pattern="1.5", repl="9", fixed=True) == "9 + 2.5"
        # Without fixed, "." matches any char — "125" would also match "1.5"
        assert regex_replace("125", pattern="1.5", repl="9") == "9"
        assert regex_replace("125", pattern="1.5", repl="9", fixed=True) == "125"

    def test_fixed_repl_backslash_literal(self) -> None:
        result = regex_replace("path", pattern="path", repl=r"C:\new", fixed=True)
        assert result == r"C:\new"

    def test_multiline_text(self) -> None:
        assert regex_replace("a\nb\na", pattern="a", repl="X") == "X\nb\nX"

    def test_japanese(self) -> None:
        assert regex_replace("株式会社テスト", pattern="株式会社", repl="(株)") == "(株)テスト"

    def test_invalid_regex_raises(self) -> None:
        with pytest.raises(ValueError, match="invalid regex"):
            regex_replace("text", pattern="(unclosed")
