# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Added
- **`strip-commas` / `sc`**: remove comma characters from text — both ASCII `,` (U+002C) and full-width `，` (U+FF0C); designed for cleaning numbers copied from the web before pasting into Excel (`1,234,567` → `1234567`)
- **`press config validate`**: parse `config.toml` and report TOML errors or future schema versions without starting the daemon; missing file is not an error
- **`press config reset [--key SECTION]`**: overwrite config with built-in defaults; creates a `.toml.bak` backup; `--key` limits reset to one section (`hotkeys`, `sql_in`, `dictionary`, `ui`, `hold`)
- **`schema_version`**: new field in `PressConfig` and generated config files (current: `1`); `config validate` rejects files with a schema version newer than the installed press

---

## [0.4.0] - 2026-05-16

### Added
- **`press daemon logs [-f] [-n N] [--level] [--json]`**: tail daemon log file; `--follow` streams new entries; `--json` outputs NDJSON
- **`press daemon status --json`**: machine-readable health check (snake_case keys, RFC 3339 timestamps, uptime in seconds)
- **Daemon logging infrastructure**: `RotatingFileHandler` (5 MB × 3 backups) writing to `%APPDATA%\press\daemon.log`; `status.json` written at daemon start
- **`check-norm` / `cn`**: inspect which Unicode normalization forms (NFC/NFD/NFKC/NFKD) the text already satisfies
- **`enlarge-kana` / `ek`**: expand small-form kana to normal size (ぁ→あ, ァ→ア) via `jaconv.enlarge_smallkana`
- **`ClipboardGuard` non-Windows stub**: allows mypy to type-check `daemon.py` on Linux

### Fixed
- **`[hotkeys.bindings]` merge**: partial bindings in `config.toml` now merge with defaults
- **`daemon_logs._passes()`**: removed redundant `lvl.upper().lower()` → `lvl.lower()`

### Changed
- **`press daemon` restructured to nested subparsers** (docker/gh style): `press daemon start|stop|status|restart|logs`
- **`press hold`**: improved `--help` text explaining CLI vs daemon dual modes
- **Dev dependencies**: bumped lower bounds — `ruff>=0.15.12`, `mypy>=2.0.0`, `pytest-mock>=3.15.1`
- **`url-encode` alias**: `ue2` → `urle` ⚠️ **breaking**
- **`url-decode` alias**: `ud2` → `urld` ⚠️ **breaking**

---

## [0.3.0] - 2026-04-25

### Added
- **Unicode normalization** (`press/transforms/unicode_norm.py`): four new commands
  - `nfc` — Normalize to NFC (canonical composition); fixes macOS NFD filenames on Windows/pCloud
  - `nfd` — Normalize to NFD (canonical decomposition)
  - `nfkc` — Normalize to NFKC (compatibility composition); collapses full-width, ligatures, etc.
  - `nfkd` — Normalize to NFKD (compatibility decomposition)
- **Line operations** (`press/transforms/lines.py`): three new parametric commands
  - `trim` / `tm` — strip trailing (and optionally leading) whitespace from each line (`--both`)
  - `dedupe` / `dq` — remove duplicate lines, insertion-order preserved (`--ignore-case`, `--adjacent`)
  - `sort` / `st` — locale-aware line sort (`--reverse`, `--numeric`, `--ignore-case`)
- **TTY clipboard default**: running `press <cmd>` in an interactive terminal without arguments
  now reads from the clipboard instead of blocking on stdin — matches the
  "copy → transform → paste" workflow
- **`-` stdin sentinel**: `press <cmd> -` forces stdin input when running interactively,
  following the Unix convention used by `cat`, `sort`, `grep`
- **Daemon hotkey bindings** for new commands: `k`=trim, `o`=dedupe, `p`=sort added to
  `_DEFAULT_BINDINGS`; `trim`/`dedupe`/`sort` registered in `CommandDispatcher._transform()`

### Changed
- `press/commands.py` added as the central command registry: `SimpleCommand` dataclass +
  `SIMPLE_COMMANDS` tuple + `SIMPLE_COMMAND_INDEX` dict shared by CLI and daemon
- `__main__.py`: removed 10 `_register_*()` boilerplate functions; replaced with
  `_register_simple_command()` factory + loop over `SIMPLE_COMMANDS` (−218 lines)
- `daemon.py`: `CommandDispatcher._transform()` match block collapsed from 32 lines to
  18 lines via `SIMPLE_COMMAND_INDEX` lookup; only parametric/special commands remain explicit
- `_add_io_args()`: unified with former `_add_dict_io_args()` via `positional: bool = True`
  parameter — eliminates duplicate argument definitions (DRY fix)
- `sort_lines()`: `locale.setlocale(LC_COLLATE, "")` moved to `main()` startup (pure function
  design principle); collation key changed from `cmp_to_key(strcoll)` to `strxfrm` (O(n) key
  generation vs O(n log n) comparisons — faster on large inputs)

### Refactored
- `mypy`: `strict_equality = true` — catches non-overlapping equality comparisons
- `ruff`: added `ARG`, `PIE`, `C4` rule categories; per-file ignore `RUF067` for
  `transforms/__init__.py` (PEP 562 lazy-loading is intentional); `ARG` suppressed for
  test files (pytest fixtures are intentionally unused)
- `_run_transform`: renamed `_cmd` → `cmd` (was misleadingly prefixed; variable is actively used)

### Dependencies
- `charset-normalizer` 3.4.6 → 3.4.7
- `Pillow` 12.1.1 → 12.2.0 (lazy plugin loading: open 2–15×, save 2–9× faster)
- `mypy` 1.19.1 → 1.20.1 (improved `match`-statement type narrowing)
- `ruff` 0.15.6 → 0.15.11 (bug fixes)
- `pytest` 9.0.2 → 9.0.3
- `pytest-cov` 7.0.0 → 7.1.0
- `hypothesis` 6.151.9 → 6.152.1

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

[Unreleased]: https://github.com/tay2501/textkit2/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/tay2501/textkit2/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/tay2501/textkit2/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/tay2501/textkit2/releases/tag/v0.1.0
