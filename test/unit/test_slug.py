"""Tests for URL slug generation."""

from press.transforms.slug import slugify


class TestSlugify:
    def test_basic(self) -> None:
        assert slugify("Hello World") == "hello-world"

    def test_punctuation_removed(self) -> None:
        assert slugify("Hello, World!") == "hello-world"

    def test_accents_folded_to_ascii(self) -> None:
        assert slugify("Café au lait") == "cafe-au-lait"

    def test_underscores_kept(self) -> None:
        assert slugify("snake_case name") == "snake_case-name"

    def test_whitespace_runs_collapse(self) -> None:
        assert slugify("a   b\tc") == "a-b-c"

    def test_existing_hyphens_collapse(self) -> None:
        assert slugify("a - b -- c") == "a-b-c"

    def test_leading_trailing_stripped(self) -> None:
        assert slugify("  --Hello--  ") == "hello"

    def test_japanese_dropped_by_default(self) -> None:
        assert slugify("日本語 title") == "title"

    def test_japanese_kept_with_unicode(self) -> None:
        assert slugify("日本語 タイトル", unicode=True) == "日本語-タイトル"

    def test_fullwidth_folded_with_unicode(self) -> None:
        # NFKC folds full-width Latin to ASCII
        assert slugify("ＡＢＣ ｄｅｆ", unicode=True) == "abc-def"

    def test_multiline_becomes_single_slug(self) -> None:
        assert slugify("first\nsecond") == "first-second"

    def test_empty(self) -> None:
        assert slugify("") == ""
