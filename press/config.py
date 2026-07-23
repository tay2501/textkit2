"""Typed configuration loader for press.

Reads ``%APPDATA%\\press\\config.toml`` using :mod:`tomllib` (Python 3.11+ stdlib)
and returns an immutable :class:`PressConfig` dataclass with typed defaults.
Missing files yield defaults; partial files merge with defaults.
"""

import tomllib
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

from press._paths import appdata_dir, press_dir

__all__ = [
    "CURRENT_SCHEMA_VERSION",
    "DictionaryConfig",
    "HoldConfig",
    "HotkeysConfig",
    "PressConfig",
    "SqlInConfig",
    "TrimConfig",
    "UiConfig",
    "binding_shadow_warnings",
    "config_reset",
    "config_validate",
    "default_config_path",
    "load_config",
    "pipeline_errors",
]

CURRENT_SCHEMA_VERSION: int = 1

# ---------------------------------------------------------------------------
# Default bindings table
# ---------------------------------------------------------------------------

# Since the alias-sequence redesign the daemon accepts any registry name or
# alias typed after the prefix (prefix + "t","m" = trim, same as `press tm`),
# so per-command default bindings are gone.  Only shift+<key> chords remain:
# they can never shadow a typed sequence (sequences are plain characters),
# and they cover the two cases a sequence serves poorly — dict_reverse has
# no CLI alias to type, and undo is a panic key that deserves one stroke.
# Single-letter user bindings still work but hide every sequence starting
# with that letter (checked first); `press config validate` warns about it.
_DEFAULT_BINDINGS: dict[str, str] = {
    "shift+d": "dict_reverse",
    "shift+z": "undo",
}


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class HotkeysConfig:
    """Hotkey prefix and key-to-command binding map."""

    prefix: str = "ctrl+shift+0"
    bindings: dict[str, str] = field(default_factory=lambda: dict(_DEFAULT_BINDINGS))


@dataclass(frozen=True, slots=True)
class SqlInConfig:
    """Options for the SQL IN-clause generator."""

    quote_char: str = "'"
    wrap: bool = False


@dataclass(frozen=True, slots=True)
class TrimConfig:
    """Options for the ``trim`` transform when dispatched by the daemon."""

    both: bool = False  # True: strip leading whitespace too (CLI --both)


@dataclass(frozen=True, slots=True)
class DictionaryConfig:
    """Dictionary lookup configuration."""

    files: tuple[str, ...] = ("%APPDATA%/press/dict/default.tsv",)

    def resolved_paths(self) -> tuple[Path, ...]:
        """Return ``files`` with ``%APPDATA%`` expanded to an absolute path."""
        appdata = str(appdata_dir())
        return tuple(Path(f.replace("%APPDATA%", appdata)) for f in self.files)


@dataclass(frozen=True, slots=True)
class UiConfig:
    """UI / tray notification settings."""

    startup_notification: bool = True
    hold_icon: bool = True
    notify_level: str = "off"  # "off" | "success" | "error" | "all"


@dataclass(frozen=True, slots=True)
class HoldConfig:
    """Options for the dual-layer clipboard hold protection."""

    monitor_clipboard: bool = True  # Layer 1: Win32 WM_CLIPBOARDUPDATE watcher
    intercept_paste_keys: bool = True  # Layer 2: pynput Ctrl+V / Shift+Insert hook


@dataclass(frozen=True, slots=True)
class PressConfig:
    """Top-level configuration object for press."""

    hotkeys: HotkeysConfig = field(default_factory=HotkeysConfig)
    sql_in: SqlInConfig = field(default_factory=SqlInConfig)
    trim: TrimConfig = field(default_factory=TrimConfig)
    dictionary: DictionaryConfig = field(default_factory=DictionaryConfig)
    ui: UiConfig = field(default_factory=UiConfig)
    hold: HoldConfig = field(default_factory=HoldConfig)
    # Named transform chains: name -> ordered registry command names.
    # Runnable via `press chain <name>` and bindable to daemon hotkeys.
    pipelines: dict[str, tuple[str, ...]] = field(default_factory=dict)
    schema_version: int = CURRENT_SCHEMA_VERSION


# ---------------------------------------------------------------------------
# Section parsers
# ---------------------------------------------------------------------------


def _parse_hotkeys(data: dict[str, Any]) -> HotkeysConfig:
    default = HotkeysConfig()
    prefix: str = data.get("prefix", default.prefix)
    raw_bindings = data.get("bindings")
    bindings = dict(_DEFAULT_BINDINGS) | (dict(raw_bindings) if raw_bindings is not None else {})
    return HotkeysConfig(prefix=prefix, bindings=bindings)


def _parse_sql_in(data: dict[str, Any]) -> SqlInConfig:
    default = SqlInConfig()
    return SqlInConfig(
        quote_char=data.get("quote_char", default.quote_char),
        wrap=data.get("wrap", default.wrap),
    )


def _parse_trim(data: dict[str, Any]) -> TrimConfig:
    default = TrimConfig()
    return TrimConfig(both=data.get("both", default.both))


def _parse_dictionary(data: dict[str, Any]) -> DictionaryConfig:
    default = DictionaryConfig()
    raw_files = data.get("files")
    files: tuple[str, ...] = tuple(raw_files) if raw_files is not None else default.files
    return DictionaryConfig(files=files)


def _parse_hold(data: dict[str, Any]) -> HoldConfig:
    default = HoldConfig()
    return HoldConfig(
        monitor_clipboard=data.get("monitor_clipboard", default.monitor_clipboard),
        intercept_paste_keys=data.get("intercept_paste_keys", default.intercept_paste_keys),
    )


def _parse_pipelines(data: dict[str, Any]) -> dict[str, tuple[str, ...]]:
    """Parse the ``[pipelines]`` table: each key maps to an array of strings.

    Non-table values and non-string steps raise ``ValueError`` so a typo is
    reported instead of silently producing a broken pipeline.
    """
    pipelines: dict[str, tuple[str, ...]] = {}
    for name, raw_steps in data.items():
        if not isinstance(raw_steps, list) or not all(isinstance(s, str) for s in raw_steps):
            raise ValueError(f"[pipelines] {name!r} must be an array of strings")
        pipelines[str(name)] = tuple(raw_steps)
    return pipelines


def _parse_ui(data: dict[str, Any]) -> UiConfig:
    default = UiConfig()
    raw_level = data.get("notify_level", default.notify_level)
    notify_level = raw_level if raw_level in ("off", "success", "error", "all") else "off"
    return UiConfig(
        startup_notification=data.get("startup_notification", default.startup_notification),
        hold_icon=data.get("hold_icon", default.hold_icon),
        notify_level=notify_level,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def default_config_path() -> Path:
    """Return the platform default config path (``%APPDATA%\\press\\config.toml``)."""
    return press_dir() / "config.toml"


def load_config(path: Path | None = None) -> PressConfig:
    """Load press configuration from a TOML file; missing file returns all defaults."""
    if path is None:
        path = default_config_path()

    try:
        with path.open("rb") as fh:
            raw: dict[str, Any] = tomllib.load(fh)
    except FileNotFoundError:
        return PressConfig()
    except tomllib.TOMLDecodeError as exc:
        raise ValueError(f"Invalid TOML in {path}: {exc}") from exc

    schema_version = int(raw.get("schema_version", CURRENT_SCHEMA_VERSION))
    hotkeys = _parse_hotkeys(raw.get("hotkeys", {}))
    sql_in = _parse_sql_in(raw.get("sql_in", {}))
    trim = _parse_trim(raw.get("trim", {}))
    dictionary = _parse_dictionary(raw.get("dictionary", {}))
    ui = _parse_ui(raw.get("ui", {}))
    hold = _parse_hold(raw.get("hold", {}))
    pipelines = _parse_pipelines(raw.get("pipelines", {}))

    return PressConfig(
        hotkeys=hotkeys,
        sql_in=sql_in,
        trim=trim,
        dictionary=dictionary,
        ui=ui,
        hold=hold,
        pipelines=pipelines,
        schema_version=schema_version,
    )


def config_validate(path: Path) -> tuple[bool, str]:
    """Validate a config file without starting the daemon.

    Returns:
        ``(True, message)`` on success; ``(False, error)`` on failure.
        A missing file is *not* an error — defaults will be used.
    """
    if not path.exists():
        return True, f"no config file at {path!r} — defaults will be used"
    try:
        with path.open("rb") as fh:
            raw: dict[str, Any] = tomllib.load(fh)
    except tomllib.TOMLDecodeError as exc:
        return False, f"TOML parse error: {exc}"
    schema = int(raw.get("schema_version", CURRENT_SCHEMA_VERSION))
    if schema > CURRENT_SCHEMA_VERSION:
        return False, (
            f"schema_version {schema} is newer than this press version supports "
            f"(current: {CURRENT_SCHEMA_VERSION}) — upgrade press or reset the config"
        )
    try:
        config = load_config(path)
    except ValueError as exc:
        return False, str(exc)
    errors = pipeline_errors(config)
    if errors:
        return False, "; ".join(errors)
    warnings = binding_shadow_warnings(config)
    if warnings:
        return True, f"{path!r}: valid (schema_version={schema}); WARNING: " + "; ".join(warnings)
    return True, f"{path!r}: valid (schema_version={schema})"


def binding_shadow_warnings(config: PressConfig) -> list[str]:
    """Warn about single-character bindings that hide typed hotkey sequences.

    A binding like ``"k" = "trim"`` fires on the first keypress, so every
    sequence starting with ``k`` (``kata``, ``kb``, …) becomes untypeable.
    Valid but worth surfacing — shift+<key> chords never collide.
    """
    from press.commands import hotkey_sequence_candidates

    candidates = hotkey_sequence_candidates(config.pipelines)
    warnings: list[str] = []
    for key in sorted(config.hotkeys.bindings):
        if len(key) != 1:
            continue
        shadowed = sorted(name for name in candidates if name.startswith(key))
        if shadowed:
            preview = ", ".join(shadowed[:4]) + ("…" if len(shadowed) > 4 else "")
            warnings.append(f"binding {key!r} hides typed sequences {preview}")
    return warnings


def pipeline_errors(config: PressConfig) -> list[str]:
    """Validate ``[pipelines]`` against the command registry.

    Thin wrapper over :func:`press.commands.validate_pipelines` — the rules and
    their wording live there, shared with the CLI ``chain`` command.  The import
    is lazy so config loading stays cheap for the delegating CLI path.
    """
    from press.commands import validate_pipelines

    return validate_pipelines(config.pipelines)


def _toml_key(key: str) -> str:
    """Return *key* as a bare or double-quoted TOML key as needed."""
    if all(c.isalnum() or c in "-_" for c in key):
        return key
    return f'"{key}"'


def _config_to_toml(config: PressConfig) -> str:
    """Serialize *config* to a TOML-formatted string."""
    lines: list[str] = [
        f"schema_version = {config.schema_version}",
        "",
        "[hotkeys]",
        f'prefix = "{config.hotkeys.prefix}"',
        "",
        "[hotkeys.bindings]",
    ]
    for k, cmd in config.hotkeys.bindings.items():
        lines.append(f'{_toml_key(k)} = "{cmd}"')
    lines += [
        "",
        "[sql_in]",
        f'quote_char = "{config.sql_in.quote_char}"',
        f"wrap = {str(config.sql_in.wrap).lower()}",
        "",
        "[trim]",
        f"both = {str(config.trim.both).lower()}",
        "",
        "[dictionary]",
        "files = [" + ", ".join(f'"{f}"' for f in config.dictionary.files) + "]",
        "",
        "[ui]",
        f"startup_notification = {str(config.ui.startup_notification).lower()}",
        f"hold_icon = {str(config.ui.hold_icon).lower()}",
        f'notify_level = "{config.ui.notify_level}"',
        "",
        "[hold]",
        f"monitor_clipboard = {str(config.hold.monitor_clipboard).lower()}",
        f"intercept_paste_keys = {str(config.hold.intercept_paste_keys).lower()}",
        "",
        "[pipelines]",
    ]
    if config.pipelines:
        for name, steps in config.pipelines.items():
            lines.append(f"{_toml_key(name)} = [" + ", ".join(f'"{s}"' for s in steps) + "]")
    else:
        lines.append('# cleanup = ["trim", "dedupe", "lf"]  # run via: press chain cleanup')
    lines.append("")
    return "\n".join(lines)


def config_reset(path: Path, *, key: str | None = None) -> bool:
    """Reset config to defaults, creating a ``.toml.bak`` backup first.

    Args:
        path: Path to ``config.toml``.
        key: Section name to reset (``hotkeys``, ``sql_in``, ``trim``,
            ``dictionary``, ``ui``, ``hold``, ``pipelines``).  ``None`` resets
            the entire file.

    Returns:
        ``True`` if a backup was created, ``False`` if no previous file existed.
    """
    backed_up = False
    if path.exists():
        path.with_suffix(".toml.bak").write_bytes(path.read_bytes())
        backed_up = True

    if key is None:
        config = PressConfig()
    else:
        try:
            existing = load_config(path)
        except (FileNotFoundError, ValueError):
            existing = PressConfig()
        match key:
            case "hotkeys":
                config = replace(existing, hotkeys=HotkeysConfig())
            case "sql_in":
                config = replace(existing, sql_in=SqlInConfig())
            case "trim":
                config = replace(existing, trim=TrimConfig())
            case "dictionary":
                config = replace(existing, dictionary=DictionaryConfig())
            case "ui":
                config = replace(existing, ui=UiConfig())
            case "hold":
                config = replace(existing, hold=HoldConfig())
            case "pipelines":
                config = replace(existing, pipelines={})
            case _:
                config = existing

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_config_to_toml(config), encoding="utf-8")
    return backed_up
