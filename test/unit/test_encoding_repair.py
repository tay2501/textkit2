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

    def test_custom_threshold_passes(self) -> None:
        """Low threshold should still accept a clearly detectable encoding."""
        original = "テスト"
        mojibake = original.encode("cp932").decode("latin-1")
        result = fix_encoding(mojibake, confidence_threshold=0.0)
        assert result == original


class TestFixEncodingErrors:
    def test_threshold_above_max_always_raises(self) -> None:
        """confidence is at most 1.0, so threshold > 1.0 always raises."""
        original = "テスト"
        mojibake = original.encode("cp932").decode("latin-1")
        with pytest.raises(ValueError, match=r"low confidence"):
            fix_encoding(mojibake, confidence_threshold=1.01)

    def test_threshold_above_actual_confidence_raises(self) -> None:
        """Mock low-chaos result and verify threshold check fires."""
        with patch("press.transforms.encoding_repair.from_bytes") as mock_from_bytes:
            mock_best = MagicMock()
            mock_best.chaos = 0.5  # confidence = 0.5
            mock_best.encoding = "cp932"
            mock_results = MagicMock()
            mock_results.best.return_value = mock_best
            mock_from_bytes.return_value = mock_results

            with pytest.raises(ValueError, match=r"low confidence"):
                fix_encoding("test", confidence_threshold=0.8)

    def test_non_latin1_raises_unicode_encode_error(self) -> None:
        """Text with code points above U+00FF cannot be re-encoded as latin-1."""
        with pytest.raises(UnicodeEncodeError):
            fix_encoding("テスト")  # already correctly decoded, not latin-1 encodable

    def test_no_encoding_detected_raises_value_error(self) -> None:
        """When charset_normalizer.from_bytes().best() returns None."""
        with patch("press.transforms.encoding_repair.from_bytes") as mock_from_bytes:
            mock_results = MagicMock()
            mock_results.best.return_value = None
            mock_from_bytes.return_value = mock_results

            with pytest.raises(ValueError, match=r"could not detect encoding"):
                fix_encoding("test")
