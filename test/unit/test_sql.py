"""Tests for SQL IN-clause conversion (F-10)."""

import pytest

from press.transforms.sql import to_sql_in


class TestToSqlIn:
    def test_basic(self) -> None:
        assert to_sql_in("USER1\nUSER2\nUSER3") == "'USER1','USER2','USER3'"

    def test_strips_whitespace(self) -> None:
        assert to_sql_in("  USER1  \n  USER2  ") == "'USER1','USER2'"

    def test_skips_blank_lines(self) -> None:
        assert to_sql_in("USER1\n\nUSER2\n\nUSER3") == "'USER1','USER2','USER3'"

    def test_single_value(self) -> None:
        assert to_sql_in("USER1") == "'USER1'"

    def test_crlf_input(self) -> None:
        assert to_sql_in("USER1\r\nUSER2") == "'USER1','USER2'"

    def test_custom_quote_char(self) -> None:
        assert to_sql_in("A\nB", quote_char='"') == '"A","B"'

    def test_wrap_option(self) -> None:
        assert to_sql_in("A\nB", wrap=True) == "('A','B')"

    def test_empty_input_raises(self) -> None:
        with pytest.raises(ValueError, match="empty"):
            to_sql_in("")

    def test_only_blank_lines_raises(self) -> None:
        with pytest.raises(ValueError, match="empty"):
            to_sql_in("\n\n\n")
