# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Changed
- `press/commands.py` added as the central command registry: `SimpleCommand` dataclass +
  `SIMPLE_COMMANDS` tuple + `SIMPLE_COMMAND_INDEX` dict shared by CLI and daemon
- `__main__.py`: removed 10 `_register_*()` boilerplate functions; replaced with
  `_register_simple_command()` factory + loop over `SIMPLE_COMMANDS` (−218 lines)
- `daemon.py`: `CommandDispatcher._transform()` match block collapsed from 32 lines to
  18 lines via `SIMPLE_COMMAND_INDEX` lookup; only parametric/special commands remain explicit

---

## [0.2.0] - 2026-04-04

### Added
- **Phase 4**: Clipboard HOLD/release (`press hold`)
  - CLI: file-based toggle at `%APPDATA%\press\hold` — persists across processes
  - Daemon: in-memory hold state with tray icon colour change (red = holding)
  - Default hotkey binding: `h` → hold toggle via `_DEFAULT_BINDINGS`
- **Phase 3**: System-tray daemon with global hotkey support (`press daemon start/stop/status/restart`)
  - Leader-key pattern: `Ctrl+Shift+F10` → binding key → transform applied to clipboard in-place
  - pystray 0.19.5 tray icon with right-click menu
  - pynput global keyboard listener with shift-state tracking
  - Singleton enforcement via Windows named mutex (`Global\press_daemon_singleton`)
  - PID file at `%APPDATA%\press\press.pid` for stop/status detection
  - Worker thread queue for non-blocking dispatch
  - Tray notifications controlled by `[ui] notify_level` config (`off`/`success`/`error`/`all`)
- `fix-encoding` (`fe`) subcommand — mojibake repair via charset-normalizer (F-15)
- `html-decode` (`hd`) subcommand — HTML entity decoding (`&amp;` → `&`)
- Typed TOML configuration loader (`press/config.py`) with frozen dataclasses and `slots=True`
- PEP 562 lazy loading in `transforms/__init__.py` for fast startup on HDD/EDR systems
- `argcomplete` shell completion support

### Changed
- mypy strict mode extended with `truthy-bool`, `redundant-expr`, `possibly-undefined` error codes
- Refactored core modules following Effective Python (3rd ed.) patterns: EAFP, generators, match statements

### Fixed
- Win32 API `argtypes`/`restype` explicit declarations for 64-bit compatibility in `clipboard.py`
- Subcommand-scoped error message format (`press <cmd>: error: ...`) for all CLI commands

### CI/CD
- Upgraded `codeql-action` to v4
- Upgraded `osv-scanner-action` to v2.3.5 with `fail-on-vuln: false`
- Added `@pytest.mark.windows_only` auto-skip in `test/conftest.py`
- Improved GitHub Actions security: pinned versions, added dependency-review workflow
- mypy target corrected to `press/` in all workflows
- Updated `astral-sh/setup-uv` to v8.0.0, `codecov/codecov-action` to v6
- Updated Semgrep container to `semgrep/semgrep`
- Fixed Windows exe build: added `--extra daemon` to include pystray/pynput/pywin32
- Added `--frozen` flag to release validation for deterministic builds

---

## [0.1.0] - 2025-12-01

### Added
- **Phase 1**: 20 CLI transform commands across 10 modules
  - `halfwidth` / `fullwidth` — full/half-width character conversion (jaconv)
  - `normalize` — whitespace normalization
  - `crlf` / `lf` / `cr` — line ending conversion
  - `underscore` / `hyphen` — separator conversion
  - `sql-in` — newline-separated values to SQL `IN` clause
  - `unicode-decode` / `unicode-encode` — `\uXXXX` escape sequences
  - `snake` / `camel` / `pascal` / `kebab` — identifier case conversion
  - `base64-encode` / `base64-decode` — Base64 codec
  - `url-encode` / `url-decode` — percent-encoding
  - `json-format` / `json-compress` — JSON pretty-print / minify
- **Phase 2**: Dictionary lookup (`press dict` — TSV-based find/replace, F-08/F-09)
- **Phase 2**: Clipboard utilities (`press clear` — clear clipboard contents)
- Common I/O flags for all transforms: `-c`/`--clip-in`, `-C`/`--clip-out`, `-v`/`--verbose`, `-q`/`--quiet`, `--fallback`
- Git-style UX: `press` with no subcommand prints help and exits 0
- Windows 11 clipboard I/O via Win32 ctypes (no third-party clipboard library)

[Unreleased]: https://github.com/tay2501/textkit2/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/tay2501/textkit2/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/tay2501/textkit2/releases/tag/v0.1.0
