"""Tests for fix_encoding transform (F-15)."""

from unittest.mock import MagicMock, patch

import pytest

from press.transforms.encoding_repair import fix_encoding


class TestFixEncodingCp932:
    def test_sjis_misread_as_latin1(self) -> None:
        """Classic mojibake: CP932 bytes decoded as latin-1."""
        original = "テスト"
        mojibake = original.encode("cp932").decode("latin-1")
        result = fix_encoding(mojibake)
        assert result == original

    def test_longer_sjis_text(self) -> None:
        original = "システム管理者"
        mojibake = original.encode("cp932").decode("latin-1")
        result = fix_encoding(mojibake)
        assert result == original

    def test_custom_threshold_still_passes(self) -> None:
        original = "テスト"
        mojibake = original.encode("cp932").decode("latin-1")
        result = fix_encoding(mojibake, confidence_threshold=0.5)
        assert result == original


class TestFixEncodingErrors:
    def test_low_threshold_raises(self) -> None:
        """confidence_threshold > 1.0 always raises."""
        original = "テスト"
        mojibake = original.encode("cp932").decode("latin-1")
        with pytest.raises(ValueError, match=r"low confidence|could not detect"):
            fix_encoding(mojibake, confidence_threshold=1.1)

    def test_non_latin1_raises_unicode_encode_error(self) -> None:
        """Text with code points above U+00FF cannot be re-encoded as latin-1."""
        with pytest.raises(UnicodeEncodeError):
            fix_encoding("テスト")  # already decoded correctly, not latin-1 encodable

    def test_no_encoding_detected_raises_value_error(self) -> None:
        """When charset_normalizer.from_bytes().best() returns None."""
        with patch("press.transforms.encoding_repair.from_bytes") as mock_from_bytes:
            mock_results = MagicMock()
            mock_results.best.return_value = None
            mock_from_bytes.return_value = mock_results

            with pytest.raises(ValueError, match=r"could not detect encoding"):
                fix_encoding("test")
