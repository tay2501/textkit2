"""Tests for press/config.py — typed config loader with TOML support."""

import textwrap
from pathlib import Path

import pytest

from press.config import (
    CURRENT_SCHEMA_VERSION,
    DictionaryConfig,
    HoldConfig,
    HotkeysConfig,
    PressConfig,
    SqlInConfig,
    TrimConfig,
    UiConfig,
    _config_to_toml,
    config_reset,
    config_validate,
    default_config_path,
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
        assert isinstance(config.trim, TrimConfig)
        assert isinstance(config.dictionary, DictionaryConfig)
        assert isinstance(config.ui, UiConfig)

        # Spot-check defaults
        assert config.hotkeys.prefix == "ctrl+shift+0"
        assert config.sql_in.quote_char == "'"
        assert config.sql_in.wrap is False
        assert config.trim.both is False
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

            [trim]
            both = true

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
        assert config.trim.both is True
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
        assert config.hotkeys.prefix == "ctrl+shift+0"
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


class TestDictionaryConfigResolvedPaths:
    """DictionaryConfig.resolved_paths() expands %APPDATA% correctly."""

    def test_resolved_paths_with_appdata(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("APPDATA", "C:/fake/AppData/Roaming")
        cfg = DictionaryConfig(files=("%APPDATA%/press/dict/default.tsv",))
        paths = cfg.resolved_paths()
        assert paths == (Path("C:/fake/AppData/Roaming/press/dict/default.tsv"),)

    def test_resolved_paths_fallback_to_home_when_appdata_missing(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.delenv("APPDATA", raising=False)
        monkeypatch.setenv("HOME", str(tmp_path))
        cfg = DictionaryConfig(files=("%APPDATA%/press/dict/default.tsv",))
        paths = cfg.resolved_paths()
        assert len(paths) == 1
        assert paths[0].name == "default.tsv"


class TestLoadConfigDefaultPath:
    """load_config(path=None) resolves path from APPDATA and returns defaults when missing."""

    def test_default_path_uses_appdata_returns_defaults(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        fake_appdata = tmp_path / "AppData" / "Roaming"
        fake_appdata.mkdir(parents=True)
        monkeypatch.setenv("APPDATA", str(fake_appdata))
        config = load_config(path=None)
        assert isinstance(config, PressConfig)
        assert config.hotkeys.prefix == "ctrl+shift+0"


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


# ---------------------------------------------------------------------------
# schema_version
# ---------------------------------------------------------------------------


class TestSchemaVersion:
    """schema_version is loaded from TOML and stored in PressConfig."""

    def test_default_schema_version(self, tmp_path: Path) -> None:
        cfg = load_config(tmp_path / "missing.toml")
        assert cfg.schema_version == CURRENT_SCHEMA_VERSION

    def test_schema_version_loaded_from_toml(self, tmp_path: Path) -> None:
        cfg_file = tmp_path / "config.toml"
        cfg_file.write_text("schema_version = 1\n", encoding="utf-8")
        cfg = load_config(cfg_file)
        assert cfg.schema_version == 1

    def test_schema_version_missing_uses_default(self, tmp_path: Path) -> None:
        cfg_file = tmp_path / "config.toml"
        cfg_file.write_text("[sql_in]\nwrap = true\n", encoding="utf-8")
        cfg = load_config(cfg_file)
        assert cfg.schema_version == CURRENT_SCHEMA_VERSION


# ---------------------------------------------------------------------------
# default_config_path
# ---------------------------------------------------------------------------


class TestDefaultConfigPath:
    def test_uses_appdata_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("APPDATA", "C:/fake/AppData")
        p = default_config_path()
        assert p == Path("C:/fake/AppData/press/config.toml")

    def test_falls_back_to_home_when_appdata_missing(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.delenv("APPDATA", raising=False)
        monkeypatch.setenv("HOME", str(tmp_path))
        p = default_config_path()
        assert p.name == "config.toml"
        assert "press" in p.parts


# ---------------------------------------------------------------------------
# config_validate
# ---------------------------------------------------------------------------


class TestConfigValidate:
    def test_missing_file_is_ok(self, tmp_path: Path) -> None:
        ok, msg = config_validate(tmp_path / "missing.toml")
        assert ok is True
        assert "defaults" in msg

    def test_valid_file_passes(self, tmp_path: Path) -> None:
        cfg_file = tmp_path / "config.toml"
        cfg_file.write_text("[sql_in]\nwrap = true\n", encoding="utf-8")
        ok, msg = config_validate(cfg_file)
        assert ok is True
        assert "valid" in msg

    def test_invalid_toml_fails(self, tmp_path: Path) -> None:
        cfg_file = tmp_path / "config.toml"
        cfg_file.write_text("not valid ][", encoding="utf-8")
        ok, msg = config_validate(cfg_file)
        assert ok is False
        assert "parse error" in msg.lower()

    def test_future_schema_version_fails(self, tmp_path: Path) -> None:
        cfg_file = tmp_path / "config.toml"
        cfg_file.write_text(f"schema_version = {CURRENT_SCHEMA_VERSION + 99}\n", encoding="utf-8")
        ok, msg = config_validate(cfg_file)
        assert ok is False
        assert "schema_version" in msg


# ---------------------------------------------------------------------------
# _config_to_toml
# ---------------------------------------------------------------------------


class TestConfigToToml:
    def test_roundtrip_defaults(self, tmp_path: Path) -> None:
        original = PressConfig()
        toml_str = _config_to_toml(original)
        cfg_file = tmp_path / "config.toml"
        cfg_file.write_text(toml_str, encoding="utf-8")
        reloaded = load_config(cfg_file)

        assert reloaded.hotkeys.prefix == original.hotkeys.prefix
        assert reloaded.hotkeys.bindings == original.hotkeys.bindings
        assert reloaded.sql_in == original.sql_in
        assert reloaded.trim == original.trim
        assert reloaded.ui == original.ui
        assert reloaded.hold == original.hold

    def test_schema_version_in_output(self) -> None:
        toml_str = _config_to_toml(PressConfig())
        assert f"schema_version = {CURRENT_SCHEMA_VERSION}" in toml_str

    def test_quoted_key_for_shift_modifier(self) -> None:
        toml_str = _config_to_toml(PressConfig())
        assert '"shift+u"' in toml_str

    def test_pipelines_roundtrip(self, tmp_path: Path) -> None:
        original = PressConfig(pipelines={"cleanup": ("trim", "dedupe", "lf")})
        cfg_file = tmp_path / "config.toml"
        cfg_file.write_text(_config_to_toml(original), encoding="utf-8")
        reloaded = load_config(cfg_file)
        assert reloaded.pipelines == {"cleanup": ("trim", "dedupe", "lf")}

    def test_empty_pipelines_emits_commented_example(self) -> None:
        toml_str = _config_to_toml(PressConfig())
        assert "[pipelines]" in toml_str
        assert '# cleanup = ["trim", "dedupe", "lf"]' in toml_str


# ---------------------------------------------------------------------------
# [pipelines] parsing and validation
# ---------------------------------------------------------------------------


class TestPipelinesConfig:
    def test_parse_pipelines_table(self, tmp_path: Path) -> None:
        cfg_file = tmp_path / "config.toml"
        cfg_file.write_text(
            '[pipelines]\ncleanup = ["trim", "dedupe", "lf"]\n',
            encoding="utf-8",
        )
        cfg = load_config(cfg_file)
        assert cfg.pipelines == {"cleanup": ("trim", "dedupe", "lf")}

    def test_default_is_empty(self, tmp_path: Path) -> None:
        assert load_config(tmp_path / "missing.toml").pipelines == {}

    def test_non_array_value_raises(self, tmp_path: Path) -> None:
        cfg_file = tmp_path / "config.toml"
        cfg_file.write_text('[pipelines]\ncleanup = "trim"\n', encoding="utf-8")
        with pytest.raises(ValueError, match="array of strings"):
            load_config(cfg_file)

    def test_non_string_step_raises(self, tmp_path: Path) -> None:
        cfg_file = tmp_path / "config.toml"
        cfg_file.write_text("[pipelines]\ncleanup = [1, 2]\n", encoding="utf-8")
        with pytest.raises(ValueError, match="array of strings"):
            load_config(cfg_file)

    def test_validate_reports_unknown_step(self, tmp_path: Path) -> None:
        cfg_file = tmp_path / "config.toml"
        cfg_file.write_text('[pipelines]\nbad = ["nope"]\n', encoding="utf-8")
        ok, msg = config_validate(cfg_file)
        assert ok is False
        assert "unknown step 'nope'" in msg

    def test_validate_passes_valid_pipeline(self, tmp_path: Path) -> None:
        cfg_file = tmp_path / "config.toml"
        cfg_file.write_text('[pipelines]\ncleanup = ["trim", "lf"]\n', encoding="utf-8")
        ok, _msg = config_validate(cfg_file)
        assert ok is True

    def test_reset_key_pipelines_clears_section(self, tmp_path: Path) -> None:
        cfg_file = tmp_path / "config.toml"
        cfg_file.write_text(
            '[sql_in]\nwrap = true\n\n[pipelines]\ncleanup = ["trim"]\n',
            encoding="utf-8",
        )
        config_reset(cfg_file, key="pipelines")
        cfg = load_config(cfg_file)
        assert cfg.pipelines == {}
        assert cfg.sql_in.wrap is True  # other sections preserved


# ---------------------------------------------------------------------------
# config_reset
# ---------------------------------------------------------------------------


class TestConfigReset:
    def test_full_reset_creates_file_when_missing(self, tmp_path: Path) -> None:
        cfg_file = tmp_path / "press" / "config.toml"
        backed_up = config_reset(cfg_file)
        assert backed_up is False
        assert cfg_file.exists()

    def test_full_reset_creates_backup_when_file_exists(self, tmp_path: Path) -> None:
        cfg_file = tmp_path / "config.toml"
        cfg_file.write_text("[sql_in]\nwrap = true\n", encoding="utf-8")
        backed_up = config_reset(cfg_file)
        assert backed_up is True
        assert cfg_file.with_suffix(".toml.bak").exists()

    def test_full_reset_writes_defaults(self, tmp_path: Path) -> None:
        cfg_file = tmp_path / "config.toml"
        cfg_file.write_text("[sql_in]\nwrap = true\n", encoding="utf-8")
        config_reset(cfg_file)
        reloaded = load_config(cfg_file)
        assert reloaded.sql_in.wrap is False  # back to default

    def test_partial_reset_key_hotkeys(self, tmp_path: Path) -> None:
        cfg_file = tmp_path / "config.toml"
        cfg_file.write_text(
            '[hotkeys]\nprefix = "ctrl+alt+f9"\n[sql_in]\nwrap = true\n',
            encoding="utf-8",
        )
        config_reset(cfg_file, key="hotkeys")
        reloaded = load_config(cfg_file)
        assert reloaded.hotkeys.prefix == "ctrl+shift+0"  # reset
        assert reloaded.sql_in.wrap is True  # other section untouched

    def test_partial_reset_key_sql_in(self, tmp_path: Path) -> None:
        cfg_file = tmp_path / "config.toml"
        cfg_file.write_text("[sql_in]\nwrap = true\nquote_char = '\"'\n", encoding="utf-8")
        config_reset(cfg_file, key="sql_in")
        reloaded = load_config(cfg_file)
        assert reloaded.sql_in.wrap is False
        assert reloaded.sql_in.quote_char == "'"

    def test_partial_reset_key_trim(self, tmp_path: Path) -> None:
        cfg_file = tmp_path / "config.toml"
        cfg_file.write_text("[trim]\nboth = true\n[sql_in]\nwrap = true\n", encoding="utf-8")
        config_reset(cfg_file, key="trim")
        reloaded = load_config(cfg_file)
        assert reloaded.trim.both is False  # reset
        assert reloaded.sql_in.wrap is True  # other section untouched

    def test_partial_reset_key_ui(self, tmp_path: Path) -> None:
        cfg_file = tmp_path / "config.toml"
        cfg_file.write_text("[ui]\nstartup_notification = false\n", encoding="utf-8")
        config_reset(cfg_file, key="ui")
        reloaded = load_config(cfg_file)
        assert reloaded.ui.startup_notification is True

    def test_partial_reset_key_hold(self, tmp_path: Path) -> None:
        cfg_file = tmp_path / "config.toml"
        cfg_file.write_text("[hold]\nmonitor_clipboard = false\n", encoding="utf-8")
        config_reset(cfg_file, key="hold")
        reloaded = load_config(cfg_file)
        assert reloaded.hold.monitor_clipboard is True

    def test_partial_reset_key_dictionary(self, tmp_path: Path) -> None:
        cfg_file = tmp_path / "config.toml"
        cfg_file.write_text(
            '[dictionary]\nfiles = ["%APPDATA%/press/dict/custom.tsv"]\n', encoding="utf-8"
        )
        config_reset(cfg_file, key="dictionary")
        reloaded = load_config(cfg_file)
        assert reloaded.dictionary == DictionaryConfig()

    def test_reset_when_existing_file_is_invalid(self, tmp_path: Path) -> None:
        cfg_file = tmp_path / "config.toml"
        cfg_file.write_text("not valid ][", encoding="utf-8")
        config_reset(cfg_file, key="ui")
        assert cfg_file.exists()
        reloaded = load_config(cfg_file)
        assert reloaded.ui == UiConfig()

    def test_hold_config_imported(self) -> None:
        assert HoldConfig().monitor_clipboard is True

    def test_unknown_key_leaves_config_unchanged(self, tmp_path: Path) -> None:
        """Passing an unrecognised key (bypassing argparse) leaves the config intact."""
        cfg_file = tmp_path / "config.toml"
        cfg_file.write_text("[sql_in]\nwrap = true\n", encoding="utf-8")
        # Directly invoke with an invalid key to exercise the `case _` branch
        config_reset(cfg_file, key="__invalid__")  # type: ignore[arg-type]
        reloaded = load_config(cfg_file)
        assert reloaded.sql_in.wrap is True  # unchanged


class TestConfigValidateEdgeCases:
    def test_valid_toml_with_internal_value_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """config_validate returns (False, …) when load_config raises ValueError."""
        cfg_file = tmp_path / "config.toml"
        cfg_file.write_text("schema_version = 1\n", encoding="utf-8")

        import press.config as cfg_mod

        original_load = cfg_mod.load_config

        def _raise(_path: Path | None = None) -> PressConfig:
            raise ValueError("simulated validation error")

        monkeypatch.setattr(cfg_mod, "load_config", _raise)
        ok, msg = config_validate(cfg_file)
        assert ok is False
        assert "simulated validation error" in msg
        monkeypatch.setattr(cfg_mod, "load_config", original_load)
