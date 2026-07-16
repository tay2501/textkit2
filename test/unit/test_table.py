"""Tests for TSV/CSV → Markdown table conversion."""

import pytest

from press.transforms.table import to_markdown_table


class TestToMarkdownTable:
    def test_tsv_basic(self) -> None:
        result = to_markdown_table("name\tage\nAlice\t30\nBob\t25\n")
        assert result == ("| name | age |\n| --- | --- |\n| Alice | 30 |\n| Bob | 25 |\n")

    def test_csv_basic(self) -> None:
        result = to_markdown_table("name,age\nAlice,30\n")
        assert result == "| name | age |\n| --- | --- |\n| Alice | 30 |\n"

    def test_tab_wins_over_comma(self) -> None:
        # Excel clipboard format is TSV; commas inside cells must survive
        result = to_markdown_table("name\tnote\nAlice\ta,b\n")
        assert "| a,b |" in result

    def test_csv_quoted_comma(self) -> None:
        result = to_markdown_table('name,note\nAlice,"x, y"\n')
        assert "| x, y |" in result

    def test_pipe_escaped(self) -> None:
        result = to_markdown_table("col\na|b\n")
        assert "| a\\|b |" in result

    def test_ragged_rows_padded(self) -> None:
        result = to_markdown_table("a\tb\tc\n1\t2\n")
        assert "| 1 | 2 |  |" in result

    def test_header_only(self) -> None:
        result = to_markdown_table("a\tb\n")
        assert result == "| a | b |\n| --- | --- |\n"

    def test_empty_raises(self) -> None:
        with pytest.raises(ValueError, match="no table data"):
            to_markdown_table("")

    def test_japanese(self) -> None:
        result = to_markdown_table("名前\t年齢\n太郎\t30\n")
        assert "| 名前 | 年齢 |" in result
        assert "| 太郎 | 30 |" in result
