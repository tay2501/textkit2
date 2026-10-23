"""Tests for regex / fixed-string replacement."""

import pytest

from press.transforms.replace import regex_replace


class TestRegexReplace:
    def test_basic(self) -> None:
        assert regex_replace("foo bar foo", patterns=["foo"], repl="baz") == "baz bar baz"

    def test_regex_pattern(self) -> None:
        assert regex_replace("a1b22c333", patterns=[r"\d+"], repl="#") == "a#b#c#"

    def test_group_reference(self) -> None:
        result = regex_replace("2026-07-17", patterns=[r"(\d+)-(\d+)-(\d+)"], repl=r"\3/\2/\1")
        assert result == "17/07/2026"

    def test_delete_matches_by_default(self) -> None:
        assert regex_replace("a-b-c", patterns=["-"]) == "abc"

    def test_missing_pattern_is_an_error(self) -> None:
        # Fails on every path — CLI, hotkey and chain step — instead of the
        # hotkey "succeeding" with a no-op while the CLI refuses.
        with pytest.raises(ValueError, match="no pattern"):
            regex_replace("unchanged", repl="X")

    def test_empty_pattern_list_is_an_error(self) -> None:
        with pytest.raises(ValueError, match="no pattern"):
            regex_replace("unchanged", patterns=[], repl="X")

    def test_several_patterns_all_match(self) -> None:
        # rg/grep -e may repeat; every pattern is searched.
        assert regex_replace("cat dog bird", patterns=["cat", "bird"], repl="_") == "_ dog _"

    def test_several_fixed_patterns(self) -> None:
        assert regex_replace("a.b a+b", patterns=["a.b", "a+b"], repl="X", fixed=True) == "X X"

    def test_group_numbers_follow_pattern_order(self) -> None:
        result = regex_replace("k=v", patterns=[r"(\w)=(\w)"], repl=r"\2=\1")
        assert result == "v=k"

    def test_ignore_case(self) -> None:
        assert regex_replace("Foo FOO foo", patterns=["foo"], repl="x", ignore_case=True) == "x x x"

    def test_case_sensitive_by_default(self) -> None:
        assert regex_replace("Foo foo", patterns=["foo"], repl="x") == "Foo x"

    def test_fixed_literal_metacharacters(self) -> None:
        assert regex_replace("1.5 + 2.5", patterns=["1.5"], repl="9", fixed=True) == "9 + 2.5"
        # Without fixed, "." matches any char — "125" would also match "1.5"
        assert regex_replace("125", patterns=["1.5"], repl="9") == "9"
        assert regex_replace("125", patterns=["1.5"], repl="9", fixed=True) == "125"

    def test_fixed_repl_backslash_literal(self) -> None:
        result = regex_replace("path", patterns=["path"], repl=r"C:\new", fixed=True)
        assert result == r"C:\new"

    def test_multiline_text(self) -> None:
        assert regex_replace("a\nb\na", patterns=["a"], repl="X") == "X\nb\nX"

    def test_japanese(self) -> None:
        assert regex_replace("株式会社テスト", patterns=["株式会社"], repl="(株)") == "(株)テスト"

    def test_invalid_regex_raises(self) -> None:
        with pytest.raises(ValueError, match="invalid regex"):
            regex_replace("text", patterns=["(unclosed"])
