"""Typed configuration loader for press.

Reads ``%APPDATA%\\press\\config.toml`` using :mod:`tomllib` (Python 3.11+ stdlib)
and returns an immutable :class:`PressConfig` dataclass with typed defaults.
Missing files yield defaults; partial files merge with defaults.
"""

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

__all__ = [
    "DictionaryConfig",
    "HoldConfig",
    "HotkeysConfig",
    "PressConfig",
    "SqlInConfig",
    "UiConfig",
    "load_config",
]

# ---------------------------------------------------------------------------
# Default bindings table
# ---------------------------------------------------------------------------

_DEFAULT_BINDINGS: dict[str, str] = {
    "w": "halfwidth",
    "f": "fullwidth",
    "n": "normalize",
    "c": "crlf",
    "l": "lf",
    "r": "cr",
    "u": "hyphen",
    "shift+u": "underscore",
    "s": "sql-in",
    "d": "dict",
    "shift+d": "dict_reverse",
    "e": "unicode-decode",
    "shift+e": "unicode-encode",
    "h": "hold",
    "z": "clear",
    "k": "trim",
    "o": "dedupe",
    "p": "sort",
}


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class HotkeysConfig:
    """Hotkey prefix and key-to-command binding map."""

    prefix: str = "ctrl+shift+f10"
    bindings: dict[str, str] = field(default_factory=lambda: dict(_DEFAULT_BINDINGS))


@dataclass(frozen=True, slots=True)
class SqlInConfig:
    """Options for the SQL IN-clause generator."""

    quote_char: str = "'"
    wrap: bool = False


@dataclass(frozen=True, slots=True)
class DictionaryConfig:
    """Dictionary lookup configuration."""

    files: tuple[str, ...] = ("%APPDATA%/press/dict/default.tsv",)

    def resolved_paths(self) -> tuple[Path, ...]:
        """Return ``files`` with ``%APPDATA%`` expanded to an absolute path."""
        appdata = os.environ.get("APPDATA", str(Path.home()))
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
    dictionary: DictionaryConfig = field(default_factory=DictionaryConfig)
    ui: UiConfig = field(default_factory=UiConfig)
    hold: HoldConfig = field(default_factory=HoldConfig)


# ---------------------------------------------------------------------------
# Section parsers
# ---------------------------------------------------------------------------


def _parse_hotkeys(data: dict[str, Any]) -> HotkeysConfig:
    """Build :class:`HotkeysConfig` from the ``[hotkeys]`` TOML table.

    Args:
        data: Mapping parsed from the ``[hotkeys]`` section.

    Returns:
        A :class:`HotkeysConfig` with per-field defaults applied.
    """
    default = HotkeysConfig()
    prefix: str = data.get("prefix", default.prefix)
    raw_bindings = data.get("bindings")
    bindings = dict(_DEFAULT_BINDINGS) | (dict(raw_bindings) if raw_bindings is not None else {})
    return HotkeysConfig(prefix=prefix, bindings=bindings)


def _parse_sql_in(data: dict[str, Any]) -> SqlInConfig:
    """Build :class:`SqlInConfig` from the ``[sql_in]`` TOML table.

    Args:
        data: Mapping parsed from the ``[sql_in]`` section.

    Returns:
        A :class:`SqlInConfig` with per-field defaults applied.
    """
    default = SqlInConfig()
    return SqlInConfig(
        quote_char=data.get("quote_char", default.quote_char),
        wrap=data.get("wrap", default.wrap),
    )


def _parse_dictionary(data: dict[str, Any]) -> DictionaryConfig:
    """Build :class:`DictionaryConfig` from the ``[dictionary]`` TOML table.

    Args:
        data: Mapping parsed from the ``[dictionary]`` section.

    Returns:
        A :class:`DictionaryConfig` with per-field defaults applied.
    """
    default = DictionaryConfig()
    raw_files = data.get("files")
    files: tuple[str, ...] = tuple(raw_files) if raw_files is not None else default.files
    return DictionaryConfig(files=files)


def _parse_hold(data: dict[str, Any]) -> HoldConfig:
    """Build :class:`HoldConfig` from the ``[hold]`` TOML table.

    Args:
        data: Mapping parsed from the ``[hold]`` section.

    Returns:
        A :class:`HoldConfig` with per-field defaults applied.
    """
    default = HoldConfig()
    return HoldConfig(
        monitor_clipboard=data.get("monitor_clipboard", default.monitor_clipboard),
        intercept_paste_keys=data.get("intercept_paste_keys", default.intercept_paste_keys),
    )


def _parse_ui(data: dict[str, Any]) -> UiConfig:
    """Build :class:`UiConfig` from the ``[ui]`` TOML table.

    Args:
        data: Mapping parsed from the ``[ui]`` section.

    Returns:
        A :class:`UiConfig` with per-field defaults applied.
    """
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


def load_config(path: Path | None = None) -> PressConfig:
    """Load press configuration from a TOML file.

    Args:
        path: Explicit path to the TOML file.  When ``None``, defaults to
            ``%APPDATA%\\press\\config.toml`` (falling back to the user home
            directory on non-Windows systems).

    Returns:
        A fully-populated :class:`PressConfig`.  Missing files yield an
        all-default instance; partial files apply defaults to unlisted fields.

    Raises:
        ValueError: If the file exists but contains invalid TOML.
    """
    if path is None:
        appdata = os.environ.get("APPDATA", str(Path.home()))
        path = Path(appdata) / "press" / "config.toml"

    try:
        with path.open("rb") as fh:
            raw: dict[str, Any] = tomllib.load(fh)
    except FileNotFoundError:
        return PressConfig()
    except tomllib.TOMLDecodeError as exc:
        raise ValueError(f"Invalid TOML in {path}: {exc}") from exc

    hotkeys = _parse_hotkeys(raw.get("hotkeys", {}))
    sql_in = _parse_sql_in(raw.get("sql_in", {}))
    dictionary = _parse_dictionary(raw.get("dictionary", {}))
    ui = _parse_ui(raw.get("ui", {}))
    hold = _parse_hold(raw.get("hold", {}))

    return PressConfig(hotkeys=hotkeys, sql_in=sql_in, dictionary=dictionary, ui=ui, hold=hold)
