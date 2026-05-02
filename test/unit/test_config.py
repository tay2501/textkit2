"""Tests for press/config.py — typed config loader with TOML support."""

import textwrap
from pathlib import Path

import pytest

from press.config import (
    DictionaryConfig,
    HotkeysConfig,
    PressConfig,
    SqlInConfig,
    UiConfig,
    load_config,
)


class TestDefaultConfigWhenFileNotFound:
    """load_config returns PressConfig defaults when the file does not exist."""

    def test_default_config_when_file_not_found(self, tmp_path: Path) -> None:
        missing = tmp_path / "nonexistent" / "config.toml"
        config = load_config(missing)

        assert isinstance(config, PressConfig)
        assert isinstance(config.hotkeys, HotkeysConfig)
        assert isinstance(config.sql_in, SqlInConfig)
        assert isinstance(config.dictionary, DictionaryConfig)
        assert isinstance(config.ui, UiConfig)

        # Spot-check defaults
        assert config.hotkeys.prefix == "ctrl+shift+f10"
        assert config.sql_in.quote_char == "'"
        assert config.sql_in.wrap is False
        assert config.ui.startup_notification is True
        assert config.ui.hold_icon is True


class TestFullConfig:
    """All TOML sections are present — every field must be loaded correctly."""

    def test_full_config(self, tmp_path: Path) -> None:
        toml_content = textwrap.dedent("""\
            [hotkeys]
            prefix = "ctrl+alt+f9"

            [hotkeys.bindings]
            w = "halfwidth"
            f = "fullwidth"

            [sql_in]
            quote_char = '"'
            wrap = true

            [dictionary]
            files = ["%APPDATA%/press/dict/custom.tsv"]

            [ui]
            startup_notification = false
            hold_icon = false
        """)
        cfg_file = tmp_path / "config.toml"
        cfg_file.write_text(toml_content, encoding="utf-8")

        config = load_config(cfg_file)

        assert config.hotkeys.prefix == "ctrl+alt+f9"
        # partial bindings merge with defaults — only overridden keys differ
        assert config.hotkeys.bindings["w"] == "halfwidth"
        assert config.hotkeys.bindings["f"] == "fullwidth"
        assert "n" in config.hotkeys.bindings  # default key preserved
        assert config.sql_in.quote_char == '"'
        assert config.sql_in.wrap is True
        assert config.dictionary.files == ("%APPDATA%/press/dict/custom.tsv",)
        assert config.ui.startup_notification is False
        assert config.ui.hold_icon is False


class TestPartialConfigSqlInOnly:
    """Only [sql_in] present — other sections must keep their defaults."""

    def test_partial_config_sql_in_only(self, tmp_path: Path) -> None:
        toml_content = textwrap.dedent("""\
            [sql_in]
            quote_char = '"'
            wrap = true
        """)
        cfg_file = tmp_path / "config.toml"
        cfg_file.write_text(toml_content, encoding="utf-8")

        config = load_config(cfg_file)

        # Overridden section
        assert config.sql_in.quote_char == '"'
        assert config.sql_in.wrap is True

        # Sections not in file remain at defaults
        assert config.hotkeys.prefix == "ctrl+shift+f10"
        assert config.ui.startup_notification is True


class TestInvalidTomlRaisesValueError:
    """Malformed TOML must raise ValueError (not TOMLDecodeError)."""

    def test_invalid_toml_raises_value_error(self, tmp_path: Path) -> None:
        cfg_file = tmp_path / "config.toml"
        cfg_file.write_text("this is not valid toml ][", encoding="utf-8")

        with pytest.raises(ValueError):
            load_config(cfg_file)


class TestCustomPath:
    """path= argument allows loading from an arbitrary location."""

    def test_custom_path(self, tmp_path: Path) -> None:
        cfg_file = tmp_path / "myconfig.toml"
        cfg_file.write_text("[sql_in]\nwrap = true\n", encoding="utf-8")

        config = load_config(path=cfg_file)
        assert config.sql_in.wrap is True


class TestBindingsKeysPreserved:
    """Binding keys are stored verbatim — no normalization applied."""

    def test_bindings_keys_preserved(self, tmp_path: Path) -> None:
        toml_content = textwrap.dedent("""\
            [hotkeys.bindings]
            "shift+u" = "underscore"
            w = "halfwidth"
        """)
        cfg_file = tmp_path / "config.toml"
        cfg_file.write_text(toml_content, encoding="utf-8")

        config = load_config(cfg_file)

        assert "shift+u" in config.hotkeys.bindings
        assert config.hotkeys.bindings["shift+u"] == "underscore"
        assert config.hotkeys.bindings["w"] == "halfwidth"


class TestHotkeyPrefix:
    """Custom prefix is loaded correctly without affecting bindings default."""

    def test_hotkeys_prefix(self, tmp_path: Path) -> None:
        toml_content = textwrap.dedent("""\
            [hotkeys]
            prefix = "ctrl+alt+space"
        """)
        cfg_file = tmp_path / "config.toml"
        cfg_file.write_text(toml_content, encoding="utf-8")

        config = load_config(cfg_file)

        assert config.hotkeys.prefix == "ctrl+alt+space"
        # bindings not specified in TOML — default must be preserved
        assert "w" in config.hotkeys.bindings
        assert config.hotkeys.bindings["w"] == "halfwidth"


class TestBindingsMerge:
    """Partial bindings in TOML are merged with defaults, not fully replaced."""

    def test_partial_bindings_merge_with_defaults(self, tmp_path: Path) -> None:
        toml_content = textwrap.dedent("""\
            [hotkeys.bindings]
            j = "sort"
        """)
        cfg_file = tmp_path / "config.toml"
        cfg_file.write_text(toml_content, encoding="utf-8")

        config = load_config(cfg_file)

        assert config.hotkeys.bindings["j"] == "sort"
        assert config.hotkeys.bindings["w"] == "halfwidth"  # default preserved
        assert config.hotkeys.bindings["f"] == "fullwidth"  # default preserved
        assert len(config.hotkeys.bindings) > 1

    def test_partial_bindings_override_default_key(self, tmp_path: Path) -> None:
        toml_content = textwrap.dedent("""\
            [hotkeys.bindings]
            w = "nfc"
        """)
        cfg_file = tmp_path / "config.toml"
        cfg_file.write_text(toml_content, encoding="utf-8")

        config = load_config(cfg_file)

        assert config.hotkeys.bindings["w"] == "nfc"  # overridden
        assert config.hotkeys.bindings["f"] == "fullwidth"  # unchanged default

    def test_empty_bindings_table_keeps_defaults(self, tmp_path: Path) -> None:
        toml_content = textwrap.dedent("""\
            [hotkeys.bindings]
        """)
        cfg_file = tmp_path / "config.toml"
        cfg_file.write_text(toml_content, encoding="utf-8")

        config = load_config(cfg_file)

        assert config.hotkeys.bindings["w"] == "halfwidth"
        assert config.hotkeys.bindings["f"] == "fullwidth"
