"""Tests for hash digest generation."""

import pytest

from press.transforms.hashing import hash_text


class TestHashText:
    def test_sha256_default(self) -> None:
        # Known vector: sha256("abc")
        assert hash_text("abc") == (
            "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
        )

    def test_empty_string(self) -> None:
        assert hash_text("") == ("e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855")

    def test_md5(self) -> None:
        assert hash_text("abc", algo="md5") == "900150983cd24fb0d6963f7d28e17f72"

    def test_sha1(self) -> None:
        assert hash_text("abc", algo="sha1") == "a9993e364706816aba3e25717850c26c9cd0d89d"

    def test_utf8_bytes_hashed(self) -> None:
        # Japanese text is hashed over its UTF-8 encoding
        import hashlib

        expected = hashlib.sha256("テスト".encode()).hexdigest()
        assert hash_text("テスト") == expected

    def test_line_endings_not_normalised(self) -> None:
        assert hash_text("a\r\nb") != hash_text("a\nb")

    def test_unknown_algo_raises(self) -> None:
        with pytest.raises(ValueError, match="unknown hash algorithm"):
            hash_text("abc", algo="nope")
