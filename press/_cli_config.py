"""CLI registration for the ``config`` command group."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import argparse

    from press._cli_helpers import _SubParsers


def _register_config_commands(sub: _SubParsers) -> None:
    """Register the ``config`` subcommand family."""
    config_p = sub.add_parser("config", help="Manage press configuration")
    config_sub = config_p.add_subparsers(dest="config_action", metavar="ACTION")
    config_p.set_defaults(func=_handle_config)

    _file_arg: dict[str, object] = {
        "metavar": "PATH",
        "default": None,
        "help": "Config file (default: platform path)",
    }

    val_p = config_sub.add_parser("validate", help="Parse config.toml and report errors")
    val_p.add_argument("--file", **_file_arg)  # type: ignore[arg-type]

    rst_p = config_sub.add_parser(
        "reset",
        help="Reset config to defaults and create a .toml.bak backup",
    )
    rst_p.add_argument(
        "--key",
        choices=["hotkeys", "sql_in", "trim", "dictionary", "ui", "hold", "type", "pipelines"],
        default=None,
        metavar="SECTION",
        help=(
            "Section to reset (hotkeys, sql_in, trim, dictionary, ui, hold, type, pipelines); "
            "omit to reset the entire file"
        ),
    )
    rst_p.add_argument("--file", **_file_arg)  # type: ignore[arg-type]


def _handle_config(args: argparse.Namespace) -> int:
    from pathlib import Path

    from press.config import config_reset, config_validate, default_config_path

    raw_file: str | None = getattr(args, "file", None)
    cfg_path = Path(raw_file) if raw_file else default_config_path()

    action: str | None = getattr(args, "config_action", None)
    if action is None:
        import subprocess

        subprocess.run([sys.argv[0], "config", "--help"], check=False)
        return 0

    match action:
        case "validate":
            ok, msg, warnings = config_validate(cfg_path)
            print(f"press config validate: {msg}", file=sys.stdout if ok else sys.stderr)
            for warning in warnings:
                print(f"press config validate: warning: {warning}", file=sys.stderr)
            return 0 if ok else 1
        case "reset":
            key: str | None = getattr(args, "key", None)
            try:
                backed_up = config_reset(cfg_path, key=key)
                if backed_up:
                    print(
                        f"press config reset: backup saved to {cfg_path.with_suffix('.toml.bak')}"
                    )
                section = f" [{key}]" if key else ""
                print(f"press config reset: config{section} reset to defaults → {cfg_path}")
                return 0
            except Exception as exc:
                print(f"press config reset: error: {exc}", file=sys.stderr)
                return 1
        case _:
            return 1
