"""Tests for line-oriented transforms: trim, dedupe, sort."""

from press.transforms.lines import dedupe_lines, sort_lines, trim_lines

# ===========================================================================
# trim_lines
# ===========================================================================


class TestTrimLines:
    def test_trailing_spaces_removed(self) -> None:
        assert trim_lines("hello   ") == "hello"

    def test_trailing_tab_removed(self) -> None:
        assert trim_lines("hello\t") == "hello"

    def test_leading_spaces_preserved_by_default(self) -> None:
        assert trim_lines("  hello") == "  hello"

    def test_both_strips_leading_and_trailing(self) -> None:
        assert trim_lines("  hello  ", both=True) == "hello"

    def test_both_empty_line_stays_empty(self) -> None:
        assert trim_lines("  ", both=True) == ""

    def test_multiline_each_line_trimmed(self) -> None:
        assert trim_lines("foo  \nbar  \nbaz  ") == "foo\nbar\nbaz"

    def test_multiline_preserves_empty_lines(self) -> None:
        assert trim_lines("foo  \n\nbar  ") == "foo\n\nbar"

    def test_multiline_both(self) -> None:
        assert trim_lines("  foo  \n  bar  ", both=True) == "foo\nbar"

    def test_trailing_newline_preserved(self) -> None:
        assert trim_lines("hello  \n") == "hello\n"

    def test_no_trailing_newline_not_added(self) -> None:
        result = trim_lines("hello  ")
        assert not result.endswith("\n")

    def test_empty_string(self) -> None:
        assert trim_lines("") == ""

    def test_only_whitespace_line(self) -> None:
        assert trim_lines("   ") == ""

    def test_only_whitespace_multiline(self) -> None:
        assert trim_lines("  \n  \n  ") == "\n\n"

    def test_crlf_normalized(self) -> None:
        result = trim_lines("foo  \r\nbar  ")
        assert result == "foo\nbar"
        assert "\r" not in result

    def test_unicode_ideographic_space_stripped(self) -> None:
        assert trim_lines("hello　") == "hello"

    def test_unicode_nbsp_stripped(self) -> None:
        assert trim_lines("hello ") == "hello"

    def test_unicode_em_space_stripped(self) -> None:
        assert trim_lines("hello ") == "hello"


# ===========================================================================
# dedupe_lines
# ===========================================================================


class TestDedupeLines:
    def test_removes_exact_duplicates(self) -> None:
        assert dedupe_lines("a\nb\na\nc") == "a\nb\nc"

    def test_first_occurrence_preserved(self) -> None:
        assert dedupe_lines("b\na\nb") == "b\na"

    def test_no_duplicates_unchanged(self) -> None:
        assert dedupe_lines("a\nb\nc") == "a\nb\nc"

    def test_insertion_order_preserved(self) -> None:
        assert dedupe_lines("c\na\nb\na\nc") == "c\na\nb"

    def test_empty_line_deduped(self) -> None:
        assert dedupe_lines("a\n\n\nb") == "a\n\nb"

    def test_empty_string(self) -> None:
        assert dedupe_lines("") == ""

    def test_single_line(self) -> None:
        assert dedupe_lines("hello") == "hello"

    def test_trailing_newline_preserved(self) -> None:
        assert dedupe_lines("a\nb\na\n") == "a\nb\n"

    def test_ignore_case_removes_variants(self) -> None:
        assert dedupe_lines("Hello\nhello\nHELLO", ignore_case=True) == "Hello"

    def test_ignore_case_preserves_original_case(self) -> None:
        assert dedupe_lines("Hello\nworld\nhello", ignore_case=True) == "Hello\nworld"

    def test_case_sensitive_by_default(self) -> None:
        assert dedupe_lines("Hello\nhello") == "Hello\nhello"

    def test_adjacent_removes_consecutive(self) -> None:
        assert dedupe_lines("a\na\nb\nb\na", adjacent=True) == "a\nb\na"

    def test_adjacent_keeps_non_consecutive(self) -> None:
        assert dedupe_lines("a\nb\na", adjacent=True) == "a\nb\na"

    def test_adjacent_with_ignore_case(self) -> None:
        assert (
            dedupe_lines("Hello\nhello\nworld", adjacent=True, ignore_case=True) == "Hello\nworld"
        )

    def test_crlf_normalized(self) -> None:
        result = dedupe_lines("a\r\nb\r\na")
        assert result == "a\nb"
        assert "\r" not in result

    def test_nfc_normalization_dedupes_equivalent(self) -> None:
        nfd = "café"  # e + combining acute
        nfc = "café"  # é precomposed
        result = dedupe_lines(f"{nfd}\n{nfc}")
        assert "\n" not in result  # 1行のみ残る

    def test_all_same_lines(self) -> None:
        assert dedupe_lines("a\na\na") == "a"


# ===========================================================================
# sort_lines
# ===========================================================================


class TestSortLines:
    def test_sorts_alphabetically(self) -> None:
        result = sort_lines("banana\napple\ncherry")
        assert result == "apple\nbanana\ncherry"

    def test_already_sorted_unchanged(self) -> None:
        assert sort_lines("a\nb\nc") == "a\nb\nc"

    def test_single_line(self) -> None:
        assert sort_lines("hello") == "hello"

    def test_empty_string(self) -> None:
        assert sort_lines("") == ""

    def test_trailing_newline_preserved(self) -> None:
        result = sort_lines("b\na\n")
        assert result == "a\nb\n"

    def test_no_trailing_newline_not_added(self) -> None:
        assert not sort_lines("b\na").endswith("\n")

    def test_reverse(self) -> None:
        assert sort_lines("a\nb\nc", reverse=True) == "c\nb\na"

    def test_numeric_sort(self) -> None:
        assert sort_lines("10\n2\n1\n20", numeric=True) == "1\n2\n10\n20"

    def test_numeric_non_numeric_lines_at_end(self) -> None:
        result = sort_lines("10\napple\n2", numeric=True)
        lines = result.split("\n")
        assert lines[0] == "2"
        assert lines[1] == "10"
        assert lines[2] == "apple"

    def test_numeric_floats(self) -> None:
        assert sort_lines("10.5\n2.1\n-1.0", numeric=True) == "-1.0\n2.1\n10.5"

    def test_numeric_reverse(self) -> None:
        assert sort_lines("1\n10\n2", numeric=True, reverse=True) == "10\n2\n1"

    def test_ignore_case(self) -> None:
        result = sort_lines("banana\nApple\ncherry", ignore_case=True)
        assert result.split("\n")[0].lower() == "apple"

    def test_empty_line_preserved(self) -> None:
        result = sort_lines("b\n\na")
        assert "" in result.split("\n")

    def test_crlf_normalized(self) -> None:
        result = sort_lines("b\r\na")
        assert result == "a\nb"
        assert "\r" not in result

    def test_stable_sort_equal_elements(self) -> None:
        assert sort_lines("a\na\na") == "a\na\na"
