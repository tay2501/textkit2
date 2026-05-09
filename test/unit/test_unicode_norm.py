"""Tests for press.transforms.unicode_norm."""

from __future__ import annotations

import unicodedata

from press.transforms.unicode_norm import check_norm, to_nfc, to_nfd, to_nfkc, to_nfkd

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# が in NFD: U+304B (か) + U+3099 (combining dakuten)
_GA_NFD = "が"
# が in NFC: U+304C (precomposed)
_GA_NFC = "が"

# フォルダ with each voiced mora in NFD (katakana + combining dakuten/handakuten)
_FOLDER_NFD = "プォルダ"
_FOLDER_NFC = unicodedata.normalize("NFC", _FOLDER_NFD)


# ---------------------------------------------------------------------------
# TestToNfc
# ---------------------------------------------------------------------------


class TestToNfc:
    def test_nfd_to_nfc(self) -> None:
        """NFD input (decomposed) must become NFC (precomposed)."""
        assert to_nfc(_GA_NFD) == _GA_NFC

    def test_already_nfc_unchanged(self) -> None:
        """NFC input must not be altered."""
        assert to_nfc(_GA_NFC) == _GA_NFC

    def test_macos_filename_dakuten(self) -> None:
        """macOS NFD filename must round-trip to NFC."""
        result = to_nfc(_FOLDER_NFD)
        assert result == _FOLDER_NFC
        assert unicodedata.is_normalized("NFC", result)

    def test_empty_string(self) -> None:
        assert to_nfc("") == ""

    def test_ascii_unchanged(self) -> None:
        assert to_nfc("hello world") == "hello world"

    def test_preserves_newlines(self) -> None:
        text = _GA_NFD + "\n" + _GA_NFD + "\n"
        result = to_nfc(text)
        assert result == _GA_NFC + "\n" + _GA_NFC + "\n"


# ---------------------------------------------------------------------------
# TestToNfd
# ---------------------------------------------------------------------------


class TestToNfd:
    def test_nfc_to_nfd(self) -> None:
        """NFC precomposed must become NFD decomposed."""
        result = to_nfd(_GA_NFC)
        assert result == _GA_NFD
        assert unicodedata.is_normalized("NFD", result)

    def test_already_nfd_unchanged(self) -> None:
        assert to_nfd(_GA_NFD) == _GA_NFD

    def test_empty_string(self) -> None:
        assert to_nfd("") == ""

    def test_ascii_unchanged(self) -> None:
        assert to_nfd("hello world") == "hello world"

    def test_preserves_newlines(self) -> None:
        text = _GA_NFC + "\nline2\n"
        result = to_nfd(text)
        assert "\n" in result
        assert result.endswith("\n")


# ---------------------------------------------------------------------------
# TestToNfkc
# ---------------------------------------------------------------------------


class TestToNfkc:
    def test_fullwidth_to_ascii(self) -> None:
        """Full-width Latin letters must become ASCII."""
        assert to_nfkc("ＡＢＣＤ") == "ABCD"

    def test_ligature_fi(self) -> None:
        """Ligature ﬁ (U+FB01) must expand to 'fi'."""
        assert to_nfkc("ﬁ") == "fi"

    def test_nfd_also_composed(self) -> None:
        """NFKC also applies canonical composition (NFC + compatibility)."""
        result = to_nfkc(_GA_NFD)
        assert result == _GA_NFC

    def test_empty_string(self) -> None:
        assert to_nfkc("") == ""

    def test_ascii_unchanged(self) -> None:
        assert to_nfkc("hello") == "hello"

    def test_preserves_newlines(self) -> None:
        result = to_nfkc("Ａ\nＢ\n")
        assert result == "A\nB\n"


# ---------------------------------------------------------------------------
# TestToNfkd
# ---------------------------------------------------------------------------


class TestToNfkd:
    def test_fullwidth_to_decomposed_ascii(self) -> None:
        """Full-width letters must decompose to ASCII via NFKD."""
        result = to_nfkd("ＡＢＣ")
        assert result == "ABC"
        assert unicodedata.is_normalized("NFKD", result)

    def test_ligature_fi(self) -> None:
        """Ligature ﬁ must expand to 'fi'."""
        assert to_nfkd("ﬁ") == "fi"

    def test_nfc_to_nfkd_decomposed(self) -> None:
        result = to_nfkd(_GA_NFC)
        assert unicodedata.is_normalized("NFKD", result)
        # Round-trip back to NFC must recover original
        assert unicodedata.normalize("NFC", result) == _GA_NFC

    def test_empty_string(self) -> None:
        assert to_nfkd("") == ""

    def test_ascii_unchanged(self) -> None:
        assert to_nfkd("hello") == "hello"

    def test_preserves_newlines(self) -> None:
        result = to_nfkd("A\nB\n")
        assert result == "A\nB\n"


# ---------------------------------------------------------------------------
# TestCheckNorm
# ---------------------------------------------------------------------------


class TestCheckNorm:
    # --- output structure ---

    def test_returns_four_lines(self) -> None:
        """Output must have exactly four non-empty lines, one per form."""
        result = check_norm("hello")
        lines = result.rstrip("\n").splitlines()
        assert len(lines) == 4

    def test_each_line_names_a_form(self) -> None:
        """Each line must start with the form name."""
        result = check_norm("hello")
        lines = result.rstrip("\n").splitlines()
        assert lines[0].startswith("NFC ")
        assert lines[1].startswith("NFD ")
        assert lines[2].startswith("NFKC")
        assert lines[3].startswith("NFKD")

    def test_ends_with_newline(self) -> None:
        assert check_norm("hello").endswith("\n")

    # --- ASCII is in all four forms ---

    def test_ascii_all_yes(self) -> None:
        result = check_norm("hello world")
        assert result.count("yes") == 4
        assert "no" not in result

    def test_empty_string_all_yes(self) -> None:
        result = check_norm("")
        assert result.count("yes") == 4

    # --- NFC input ---

    def test_nfc_text_nfc_yes_nfd_no(self) -> None:
        # が (U+304C) is NFC-precomposed; not NFD-canonical
        ga_nfc = "が"
        result = check_norm(ga_nfc)
        lines = {ln.split()[0]: ln.split()[1] for ln in result.rstrip("\n").splitlines()}
        assert lines["NFC"] == "yes"
        assert lines["NFD"] == "no"
        assert lines["NFKC"] == "yes"
        assert lines["NFKD"] == "no"

    # --- NFD input ---

    def test_nfd_text_nfd_yes_nfc_no(self) -> None:
        # か (U+304B) + combining dakuten (U+3099) = NFD form of が
        ga_nfd = "が"
        result = check_norm(ga_nfd)
        lines = {ln.split()[0]: ln.split()[1] for ln in result.rstrip("\n").splitlines()}
        assert lines["NFD"] == "yes"
        assert lines["NFC"] == "no"

    # --- compatibility characters (NFKC/NFKD) ---

    def test_fullwidth_not_in_nfkc(self) -> None:
        # U+FF21 FULLWIDTH LATIN CAPITAL LETTER A is a compatibility character — not NFKC-normalised
        result = check_norm("Ａ")
        lines = {ln.split()[0]: ln.split()[1] for ln in result.rstrip("\n").splitlines()}
        assert lines["NFKC"] == "no"
        assert lines["NFKD"] == "no"

    def test_ligature_fi_not_in_nfkc(self) -> None:
        # ﬁ (U+FB01) is a compatibility ligature
        result = check_norm("ﬁ")
        lines = {ln.split()[0]: ln.split()[1] for ln in result.rstrip("\n").splitlines()}
        assert lines["NFKC"] == "no"
        assert lines["NFKD"] == "no"

    # --- round-trip consistency with is_normalized ---

    def test_consistent_with_unicodedata_is_normalized(self) -> None:
        """check_norm must agree with unicodedata.is_normalized for every form."""
        samples = ["hello", "が", "が", "Ａ", "ﬁ", ""]
        for text in samples:
            result = check_norm(text)
            lines = {ln.split()[0]: ln.split()[1] for ln in result.rstrip("\n").splitlines()}
            for form in ("NFC", "NFD", "NFKC", "NFKD"):
                expected = "yes" if unicodedata.is_normalized(form, text) else "no"
                assert lines[form] == expected, f"{form!r} mismatch for {text!r}"
