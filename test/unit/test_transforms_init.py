"""Tests for press.transforms package lazy loading (PEP 562 __getattr__)."""

import pytest

import press.transforms as _t


class TestLazyLoading:
    """Verify that press.transforms exposes all public functions via __getattr__."""

    def test_all_exports_are_callable(self) -> None:
        """Every name in __all__ must be importable and callable."""
        for name in _t.__all__:
            fn = getattr(_t, name)
            assert callable(fn), f"press.transforms.{name} should be callable"

    def test_unknown_attribute_raises(self) -> None:
        """Accessing a name not in __all__ must raise AttributeError."""
        with pytest.raises(AttributeError, match="has no attribute 'no_such_fn'"):
            _ = _t.no_such_fn

    def test_cached_after_first_access(self) -> None:
        """Attribute should be cached in module __dict__ after first access."""
        # Access once to trigger __getattr__ and populate cache
        _ = _t.to_halfwidth
        # After access, the name must live directly in the module namespace
        assert "to_halfwidth" in vars(_t)

    def test_to_halfwidth_works(self) -> None:
        """Lazy-loaded to_halfwidth should produce correct output."""
        assert _t.to_halfwidth("ａｂｃ１２３") == "abc123"

    def test_normalize_whitespace_works(self) -> None:
        """Lazy-loaded normalize_whitespace should produce correct output."""
        assert _t.normalize_whitespace("hello   world") == "hello world"

    def test_to_sql_in_works(self) -> None:
        """Lazy-loaded to_sql_in should produce correct output."""
        assert _t.to_sql_in("a\nb\nc") == "'a','b','c'"
