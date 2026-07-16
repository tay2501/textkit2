# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Added
- **`press undo`**: restore the clipboard text the last clipboard-writing press command (`-C` transform or `clear`) overwrote; running it again swaps back (redo). Single-slot snapshot, DPAPI-encrypted at `%APPDATA%\press\undo.txt`; content carrying the sensitive-exclusion formats (genpass passwords, KeePassXC/Bitwarden copies) is never captured; `PRESS_NO_UNDO=1` disables the snapshot write. The daemon keeps its own in-memory slot for hotkey transforms (default binding `Shift+Z`) — the same dual-layer design as hold. Decision record: `docs/dev/clipboard-history-decision-2026-07-17.md` §7
- **`unix-to-date` / `u2d` and `date-to-unix` / `d2u`**: Unix time ⇔ ISO 8601 conversion applied per line; seconds vs. milliseconds auto-detected by magnitude, naive dates read as local time, `--utc` / `--ms` output switches
- **`slug` / `sl`**: Django-style URL slug (lowercase, hyphens, NFKD ASCII folding); `--unicode` keeps non-ASCII word characters for Japanese slugs
- **`press uuid`**: random UUID v4 generator (`-n` count, `-U` uppercase, `-C` clipboard), completing the generator pair with `genpass`
- **`katakana` / `kata` and `hiragana` / `hira`**: hiragana ⇔ katakana conversion via the already-bundled jaconv (`ひらがな` → `ヒラガナ`), closing the most-requested Japanese gap against Clibor-style tools
- **`hash` / `hs`**: hex digest of the text over its UTF-8 bytes (`--algo sha256|sha1|sha512|md5|…`, default SHA-256); line endings are hashed as-is, matching `sha256sum` semantics
- **`replace` / `rp`**: regex search & replace with `\1` group references (`--pattern/--repl/--ignore-case`); `--fixed` switches to literal-string mode for users who don't speak regex — the press equivalent of Clibor's 整形 replacement
- **`count` / `wc`**: character / word / line / UTF-8 byte report; `non-space` count excludes all whitespace for Japanese manuscript counting
- **`html-encode` / `he`**: escape `& < > " '` to HTML entities — the missing inverse of the existing `html-decode`
- **`markdown-table` / `mdt`**: TSV/CSV → Markdown table with auto-detected delimiter (tab wins, so an Excel-copied range converts directly); quoted CSV fields and `|` escaping handled
- **`number-lines` / `nl`** (`--start`, `--sep`) and **`reverse-lines` / `rl`**: line numbering and line-order reversal, rounding out the line-operations group
- Competitive gap analysis behind the above: `docs/dev/feature-gap-analysis-2026-07-17.md` (PowerToys Advanced Paste, DevToys 2.0, CopyQ, Clibor, Boop surveyed; rejected candidates documented with reasons)
- **`press chain` / `ch`**: apply multiple transforms in one invocation (`press chain trim dedupe lf`) — one input read, one output write, one process launch instead of one per step. Aliases resolve; any unknown or failing step aborts before anything is written
- **`[pipelines]` config section**: named step lists (`cleanup = ["trim", "dedupe", "lf"]`) runnable via `press chain cleanup`, discoverable via `press chain --list`, and bindable to daemon hotkeys like any built-in command. `press config validate` reports unknown steps, command-name collisions, empty pipelines, and nesting; `press config reset --key pipelines` clears the section. Closes the workflow gap against CopyQ scripting / PowerToys Advanced Paste custom actions with plain TOML instead of a scripting language
- **Daemon delegation**: while `press daemon` is running, `press <command>` sends the text to it over a per-user named pipe instead of importing the transform module. On EDR/DLP machines this caps every command at the same file-open cost (`fix-encoding`: 155 → 55 opens, 151 ms → 100 ms). Falls back to the in-process transform when no daemon answers; `PRESS_NO_DAEMON=1` opts out
- **Code signing pipeline**: `release.yml` submits the Windows executable to SignPath, dormant until the SignPath Foundation application is approved and the `SIGNPATH_*` repository variables are set. Code signing policy published in `docs/dev/code-signing.md`
- **Python 3.15 pre-release CI lane** (GA 2026-10-01) to catch pystray/pynput breakage early; `requires-python` widened to `>=3.13,<3.16`
- **`underscore` aliases `underbar` / `ub`**: syntactic-sugar aliases for the existing hyphens → underscores transform, matching the Japanese name for the `_` character ("アンダーバー"); available in both CLI and daemon dispatch
- **`digits-only` / `dg`**: keep only digit characters — removes currency symbols, commas, periods, spaces, and any other non-digit content; retains both half-width `0-9` and full-width `０-９` as-is (`¥1,234` → `1234`, `€1.234` → `1234`, `１２３円` → `１２３`); handles international amount formats where comma and period roles are swapped
- **`strip-commas` / `sc`**: remove comma characters from text — both ASCII `,` (U+002C) and full-width `，` (U+FF0C); designed for cleaning numbers copied from the web before pasting into Excel (`1,234,567` → `1234567`)
- **`press config validate`**: parse `config.toml` and report TOML errors or future schema versions without starting the daemon; missing file is not an error
- **`press config reset [--key SECTION]`**: overwrite config with built-in defaults; creates a `.toml.bak` backup; `--key` limits reset to one section (`hotkeys`, `sql_in`, `dictionary`, `ui`, `hold`)
- **`schema_version`**: new field in `PressConfig` and generated config files (current: `1`); `config validate` rejects files with a schema version newer than the installed press
- **`press clear --hold`**: also discard the saved `press hold` file without restoring it to the clipboard
- **ClipboardGuard auto-release on clipboard wars**: the WM_CLIPBOARDUPDATE monitor now counts restores — more than 15 within 3 seconds means another resident tool (clipboard history manager, sync agent) is rewriting the clipboard, so the guard stands down and notifies via the tray instead of fighting forever

### Fixed
- **Linux mypy CI lane repaired** (red since the pipe-delegation hardening on 2026-07-12): Win32-only helpers (`_load_kernel32`, `_read_message`) gained platform guards so the Ubuntu lane prunes their `ctypes.WinDLL` / `get_last_error` references; the duplicate mutex kernel32 block in `daemon/_lifecycle.py` was consolidated into the shared `press._pipe._load_kernel32` loader; a now-unused `type: ignore[no-redef]` was removed; the `warn_unreachable` opt-out was extended from `press.daemon.*` to the other platform-gated modules (`press._pipe`, `press.clipboard`, `press._dpapi`)
- **Clipboard writes no longer fail silently**: `EmptyClipboard` / `SetClipboardData` return values are now checked — on failure the command reports an error (exit 1) instead of claiming success while the old clipboard content is still in place, and the `GlobalAlloc` buffer is freed (its ownership only passes to the system when `SetClipboardData` succeeds)
- **Correct LRESULT width on x64**: the clipboard-monitor window procedure and `DefWindowProcW` / `DispatchMessageW` declarations use pointer-sized `c_ssize_t` instead of 32-bit `c_long`, which truncated pointer-valued results
- **Clipboard-monitor message loop exits on `GetMessageW` error** (return value `-1`) instead of busy-looping on a persistent error
- **Pipe client timeout no longer leaks the worker's pipe handle**: when the daemon fails to answer within the deadline, the blocked synchronous I/O is cancelled (`CancelSynchronousIo`) so the worker thread releases its handle instead of holding it for the process lifetime

### Security
- **`genpass --clear-after SEC`**: KeePassXC-style conditional auto-clear — the clipboard is wiped after SEC seconds *only if it still holds the password* (checked via `GetClipboardSequenceNumber` while the clipboard is held open, so the check-and-clear is atomic); content copied by another app in the meantime is left untouched. New `clipboard.get_clipboard_sequence_number()` / `clear_clipboard_if_unchanged()` APIs
- **Secrets now also set the `Clipboard Viewer Ignore` format**: the classic cooperative opt-out honoured by Ditto / ClipboardFusion-era clipboard managers, complementing the Win+V-era exclusion formats below
- **`genpass` passwords are excluded from Win+V history and Cloud Clipboard sync**: clipboard writes gained `sensitive=True`, which sets the `ExcludeClipboardContentFromMonitorProcessing`, `CanIncludeInClipboardHistory` (0) and `CanUploadToCloudClipboard` (0) formats — the same exclusion password managers use. If the marking fails, the clipboard is wiped and the command errors rather than leaving the secret unmarked
- **The hold file is DPAPI-encrypted**: `press hold` stores clipboard text encrypted for the current Windows user (`CryptProtectData`, ctypes-only — no pywin32 dependency for the base CLI) instead of plaintext under `%APPDATA%`, keeping held text out of backups and profile sync. Legacy plaintext hold files are still restored; the fallback will be removed after one release
- **Security CI now gates**: pip-audit and OSV-Scanner fail the build on known vulnerabilities in the locked dependency set (previously all scanners were advisory-only via `|| true`); Bandit and Semgrep stay advisory by design (SAST false-positive rate) with findings in the Security tab. All GitHub Actions across every workflow are now pinned to full commit SHAs (previously first-party actions used mutable tags)
- **Lockfile refresh clears all pip-audit and OSV findings**: pip 26.1.2, urllib3 2.7.0, Pillow 12.3.0, idna 3.18, msgpack 1.2.1, click 8.4.2, setuptools 83.0.0, soupsieve 2.8.4, starlette 1.3.1 (OSV scans the full `uv.lock` including the docs/build dependency groups, wider than pip-audit's synced-environment audit)
- **Daemon singleton mutex is now per-user** (`Global\press_daemon_singleton_<user>`), matching the per-user pipe name and PID file. Previously the machine-wide name meant one user's daemon — or a deliberately squatted mutex — blocked every other user's daemon on a shared machine, and `daemon status` misreported another user's daemon as running. **Upgrade note**: run `press daemon stop` *before* upgrading; a daemon started under the old name cannot prevent a new one from double-starting
- **Named-pipe delegation hardened against local pipe-squatting**: the daemon's pipe now carries an explicit owner-only DACL (`D:P(A;;GA;;;OW)`) instead of Windows' default descriptor, which grants `Everyone`/anonymous read access; the first pipe instance sets `FILE_FLAG_FIRST_PIPE_INSTANCE` so a name already owned by another process is detected (logged, delegation disabled) rather than silently shared; the CLI verifies the pipe server's PID against the daemon PID file (`GetNamedPipeServerProcessId`) before sending any clipboard text and opens the pipe with `SECURITY_SQOS_PRESENT` at anonymous impersonation level so a rogue server cannot impersonate the caller's token
- **`press daemon stop` guards against PID recycling**: a stale PID file whose PID now belongs to an unrelated process (name not `python*`/`press*`) is treated as stale and removed instead of terminating that process
- **Reliable `GetLastError` via ctypes**: Win32 helpers now load kernel32 with `WinDLL(use_last_error=True)` and read `ctypes.get_last_error()` per the official ctypes guidance, and declare `CreateMutexW`/HANDLE return types as `c_void_p` so 64-bit handles are not truncated

### Changed
- **Dictionary TSV format specified as UTF-8 / CRLF / no BOM**: `press dict add` / `remove` now write this canonical format on every platform (previously line endings were platform-dependent); the reader leniently strips a UTF-8 BOM (Notepad/Excel save artifact) and accepts LF, so the first key no longer silently fails to match in BOM-prefixed files
- **PEP 639 license metadata**: `license = "MIT"` SPDX expression + `license-files`, deprecated `License ::` classifier removed; wheels now carry `License-Expression` (Metadata-Version 2.4) with `LICENSE` bundled under `dist-info/licenses/`; hatchling pinned to `>=1.27`
- **CI/CD hardening**: third-party actions (setup-uv, codecov, action-gh-release, osv-scanner) pinned to full commit SHAs per GitHub secure-use guidance; `uv sync --frozen` → `--locked` so CI fails on a stale lockfile; security workflow now audits the same locked, all-extras dependency set as CI; codecov deprecated `file:` input → `files:`
- **ruff `target-version` removed**: inferred from `requires-python` (single source of truth)
- **Coverage denominator widened**: `_cli_*.py`, `clipboard.py`, `daemon/_lifecycle.py` and `daemon/_pipe.py` are now measured (previously omitted along with all I/O code); platform-gated `if sys.platform == "win32":` blocks are excluded on both CI lanes for a comparable percentage, with their internals unit-tested through fakes. The gate is interim-set to 74% — the binding Ubuntu lane measures 74.80% (79 `windows_only` tests skip there; Windows measures 81.65%) — to be ratcheted up as CLI handler tests accumulate; the previous 80% was measured against a denominator that omitted all I/O code

### Removed
- **PyPI publish job**: the name `press` is occupied on PyPI by an unrelated package, so the job only ever skipped silently; distribution is via GitHub Releases (wheel + sdist + Windows zip + SHA-256 checksums)

### Refactored
- **`daemon.py` split into a package** (863 lines → `press/daemon/` with `_backends`, `_tray`, `_hotkeys`, `_dispatch`, `_lifecycle`, `_logs`, `_pipe`, `_service`); public API (`run_daemon`, `stop_daemon`, `daemon_status`, `daemon_logs`) unchanged
- **pystray/pynput confined to `daemon/_backends.py`** behind `TrayIcon` / `KeyListener` Protocols, so replacing the unmaintained pystray touches one module
- **`__main__.py` decomposed** into focused CLI modules: `_cli_helpers.py` (shared I/O), `_cli_dict.py` (dict commands), `_cli_config.py` (config commands), `_cli_daemon.py` (daemon commands) — `__main__.py` retains only parser construction and entry point
- **`sql-in` deduplication**: input values are deduplicated and sorted before building the `IN` clause
- **Bug fixes**: corrected `_LAZY` omissions in `transforms/__init__.py` (missing `strip_commas`, `digits_only`); removed duplicate `except` clause; trimmed redundant docstrings

### Dependencies
- Bump pynput to `>=1.8.2`
- Bump pywin32 to `>=312`
- Bump pytest to `>=9.1.1`
- Bump hypothesis to `>=6.155.7`
- Bump ruff to `>=0.15.18`
- Bump mypy to `>=2.1.0`
- Bump pip-audit to `>=2.10.1`
- Bump myst-parser to `>=5.1.0`
- Bump pyinstaller to `>=6.21.0`

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
