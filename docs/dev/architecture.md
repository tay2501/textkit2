# Architecture

## Overview

`press` has two independent entry points sharing the same transform core.

```
┌─────────────────────────────────────┐   ┌──────────────────────┐
│  press daemon                       │   │  press CLI            │
│  (long-running, Windows only)       │   │  (one-shot)           │
│                                     │   │                       │
│  _hotkeys.HotkeyManager             │   │  argparse             │
│    pynput GlobalHotKeys             │   │    ↓                  │
│    LeaderKeyListener                │   │  _run_transform()     │
│    ↓                                │   │    ↓                  │
│  _hotkeys._WorkerThread (queue)     │   │  _pipe.try_delegate() │
│    ↓                                │◀──┼──── named pipe ───────┤
│  _dispatch.CommandDispatcher        │   │    ↓ (or local)       │
│    ↓                                │   │  stdout / clipboard   │
│  clipboard.py (Win32 ctypes)        │   └──────────────────────┘
│  _backends.py → pystray / pynput    │
└─────────────────────────────────────┘
              ↓ shared
┌─────────────────────────────────────┐
│  press/commands.py                  │
│  SIMPLE_COMMANDS / PARAMETRIC_…     │
│  SPECIAL_COMMANDS, resolve_spec()   │
└─────────────────────────────────────┘
              ↓ shared
┌─────────────────────────────────────┐
│  press/transforms/                  │
│  (pure functions, no I/O)           │
│                                     │
│  width.py      kana.py              │
│  whitespace.py lineending.py        │
│  lines.py      separator.py         │
│  case.py       encode.py            │
│  escape.py     encoding_repair.py   │
│  unicode_norm.py  json_fmt.py       │
│  sql.py        table.py             │
│  replace.py    hashing.py           │
│  stats.py      slug.py              │
│  timestamp.py  dictionary.py        │
│                                     │
│  stash.py / undo.py — slot files    │
│  (the only modules here with I/O)   │
└─────────────────────────────────────┘
```

When the daemon is running, the CLI offers each transform to it over a named
pipe instead of importing the transform module — see
[Daemon delegation](#daemon-delegation-named-pipe).

## Module responsibilities

| Module | Responsibility |
|--------|----------------|
| `__main__.py` | Top-level argparse (`_Parser`, `allow_abbrev=False`), transform-command registration from the registry, `clear`/`undo`/`genpass`/`uuid` handlers, UTF-8 I/O setup |
| `_cli_helpers.py` | Shared CLI I/O: `_read_input`, `_write_output`, `_run_transform`, `_add_io_args`, the undo snapshot before a `-C` write |
| `_cli_chain.py` / `_cli_dict.py` / `_cli_config.py` / `_cli_stash.py` / `_cli_daemon.py` / `_cli_trace.py` / `_cli_notify.py` | One module per command group (`chain`, `dict`, `config`, `stash`, `daemon`, `trace`, `notify`) |
| `_cli_catalog.py` | Grouped command listing and "did you mean" for an unknown command; imported only on that error path |
| `commands.py` | Declarative registry: `SimpleCommand` / `ParametricCommand` (+ `CliArg`) transforms, `SpecialCommand` rows for non-transform commands, `TRANSFORM_CATEGORIES` for display order, and `resolve_spec()` as the only name/alias lookup. Single source of truth for the CLI, the daemon, the pipe server and `chain` |
| `clipboard.py` | Win32 ctypes clipboard API — `get_clipboard_text`, `set_clipboard_text(…, sensitive=)`, `clear_clipboard`, `clipboard_has_sensitive_marks`, and `ClipboardGuard` (hold) |
| `keystrokes.py` | Win32 `SendInput` synthesis for the `type` command — pure `plan_keystrokes()` plus a Windows-only `type_text()` |
| `config.py` | TOML loader → frozen `PressConfig` dataclass hierarchy (`slots=True`); the `_SECTIONS` registry drives loading, `config reset`, and serialization from one table |
| `genpass.py` | `generate_password()` over the stdlib `secrets` module |
| `_dpapi.py` | User-scoped DPAPI `protect` / `unprotect` for `stash.txt` and `undo.txt` (Windows only) |
| `_notify.py` | The `notify-off` marker-file switch shared by `press notify` and the daemon |
| `_paths.py` | Single source for `%APPDATA%\press` locations |
| `_version.py` | Single source for the installed version string; absorbs both shapes of a damaged install (`PackageNotFoundError`, and 3.15's `MetadataNotFound`) |
| `_pipe.py` | Named-pipe protocol + CLI client (`try_delegate`), the single kernel32 loader, and `user_name()` for per-user object names; deliberately import-light |
| `daemon/` | Windows daemon package (see below); public API is `run_daemon`, `start_daemon`, `stop_daemon`, `daemon_status`, `daemon_logs` |
| `dictionary.py` | TSV file CRUD — `add_entry`, `remove_entry`, `list_entries` — and `configured_dict_path()`, the one answer to "which file" for both CLI and daemon |
| `transforms/` | Pure `str → str` functions, one module per domain; no I/O or side effects (`stash.py` / `undo.py` are the file-slot exceptions) |
| `transforms/lines.py` | Line-oriented operations: `trim_lines`, `dedupe_lines`, `sort_lines`, `number_lines`, `reverse_lines` |
| `transforms/lineending.py` | CRLF/CR/LF conversion — and the **single definition of what counts as a line ending**; `lines.py`, `timestamp.py`, `sql.py`, `whitespace.py` and `keystrokes.py` all normalise through its `to_lf` |
| `transforms/unicode_norm.py` | Unicode normalization: `to_nfc`, `to_nfd`, `to_nfkc`, `to_nfkd`, `check_norm` |
| `transforms/stash.py` | One-slot stash file (`push` / `pop` / `drop` / `stashed`) and the slot-file format shared with undo |
| `transforms/undo.py` | Undo snapshot (`save_snapshot`, `swap_undo`) and `snapshot_allowed()`, the single rule for when press may keep a copy |

### The `daemon/` package

| Module | Responsibility |
|--------|----------------|
| `_backends.py` | **The only importer of pystray and pynput**, behind `TrayIcon` / `KeyListener` Protocols |
| `_tray.py` | Tray icon image generation (Pillow) |
| `_hotkeys.py` | Prefix hotkey, leader-key listener lifecycle, `_WorkerThread` |
| `_sequence.py` | `SequenceResolver` — **pure** typed-sequence rules (stdlib only, no threads) |
| `_dispatch.py` | `CommandDispatcher` — clipboard transforms, hold toggle, in-memory undo slot, and `_notify()`, the only caller of `icon.notify` |
| `_notifications.py` | `notifications_allowed()` — the `press notify off` switch plus Windows' `SHQueryUserNotificationState` (busy / presentation / full-screen) |
| `_lifecycle.py` | Singleton mutex, PID/status files, `start_daemon`, `stop_daemon`, `daemon_status` |
| `_logs.py` | Rotating log setup, `daemon_logs` |
| `_pipe.py` | Named-pipe server answering delegated CLI transforms |
| `_service.py` | `run_daemon` — wires the above together |

pystray has had no release since 2023, so confining it to `_backends.py` keeps
a future replacement (ctypes `Shell_NotifyIcon`) to a single-module change.

## Key design decisions

| Decision | Rationale |
|---|---|
| `commands.py` central registry | Single source of truth for command→function mapping; CLI and daemon both derive from it, eliminating duplication |
| No DI framework | Function arguments are sufficient at this scale |
| No async | Win32 message loop handles event dispatch; asyncio adds no value |
| No ORM | TSV dictionary is an in-memory `dict` loaded on demand |
| `transforms/` are pure functions | No side effects = trivially testable in isolation |
| OS-specific code isolated | `clipboard.py` holds the clipboard Win32 calls, `keystrokes.py` the input-synthesis ones; `daemon/_backends.py` holds every pystray/pynput call |
| Flat package structure | Single `press/` package; no Polylith components/bases split |
| `tomllib` for config | Python 3.11+ standard library; no Pydantic needed |
| Lazy imports everywhere | PEP 562 `__getattr__` in `transforms/__init__.py`; deferred imports in `__main__.py` and the daemon package reduce startup time on HDD/EDR-monitored systems |
| Daemon delegation over a named pipe | Skips the transform module import entirely when a daemon is running (see below) |
| PyInstaller `--onedir` | `--onefile` re-extracts on every run; `--onedir` is cached by EDR after first run |

## Command registration flow

Both **simple** commands (signature `fn(text: str) -> str`) and **parametric**
commands (extra CLI flags declared as `CliArg` entries) live in one registry:

```
press/commands.py
  └── SIMPLE_COMMANDS / PARAMETRIC_COMMANDS
            │
     ┌──────┴──────────┐
     │                 │
__main__.py     daemon/_dispatch.py
_register_      CommandDispatcher
transform_      .transform()
command (loop)    (index lookup)
```

Adding either kind of command:

1. Write the transform function in `press/transforms/<domain>.py`
2. Add a `SimpleCommand(...)` or `ParametricCommand(...)` entry in `commands.py`
   (parametric: declare options via `cli_args`; use `daemon_kwargs` for
   config-driven arguments during daemon hotkey dispatch)
3. A new transforms **module** also needs a row in `TRANSFORM_CATEGORIES`,
   which decides where its commands appear in `press --help`

The lazy exports in `transforms/__init__.py` are built from both registries
(`_build_lazy()`); only helpers outside them go in `_EXTRA`.

Non-transform commands (`clear`, `stash`, `undo`, `dict`, `genpass`, `uuid`,
`chain`, and the daemon-only `hold`, `dict-reverse`, `type`, `notify-off`,
`notify-on`) are one `SpecialCommand` row each in `SPECIAL_COMMANDS`. Their
argparse aliases, the daemon's typeable names, and `DAEMON_SPECIAL_COMMANDS`
all derive from that table; `hotkey=True` also requires wiring in
`CommandDispatcher`.

Every name or alias lookup goes through `commands.resolve_spec()`, so an alias
added to a registry row works in the CLI, the daemon, the pipe server and
`chain` at once. Renaming a command or a transform keyword requires bumping
`_pipe.PROTOCOL_VERSION` (see below).

## Prefix key state machine

```
[IDLE]
  │  prefix chord pressed simultaneously (default: Ctrl+Alt+K)
  ▼
[TYPING]  ─── 2 s inactivity, Esc, or 10 s hard limit ──→ [IDLE]
  │  keys accumulate: a [hotkeys.bindings] entry on the first key,
  │  otherwise a command name or alias ("t","m" → trim)
  ▼
[EXECUTING] → transform clipboard in-place → [IDLE]
```

Responsibilities are split so the rules can be tested without concurrency:

- `_sequence.SequenceResolver` is **pure** — characters in, a queue item or
  "keep listening" out. It owns the buffer, the ambiguity rule (an exact match
  that a longer name extends is held pending), and binding precedence.
- `_hotkeys.LeaderKeyListener` owns the machinery: the pynput listener, shift
  tracking, the timeout watcher, and the once-only handoff to the queue.

The listener swallows the keys it consumes so typed characters do not leak into
the focused window — which also means they are consumed rather than delivered.
It does **not** use pynput's blanket `suppress=True`: a low-level hook runs
before Windows updates the async key state, so swallowing the prefix chord's
key-ups left Ctrl/Shift logically held. A `win32_event_filter` driven by
`_sequence.KeySuppression` swallows only the presses the leader consumed and
their releases, and lets modifiers through. Because every keystroke re-arms the inactivity timeout, a second,
non-re-armable `_LEADER_HARD_LIMIT` bounds how long press can hold the keyboard
at all; it is a safety valve, not part of the interaction.

Results are enqueued for the `_WorkerThread` so the OS hotkey callback returns
immediately.

## Daemon delegation (named pipe)

On EDR/DLP-monitored machines, `press <cmd>` is dominated not by the transform
(≤2 ms) but by the file opens the interpreter makes while importing the
transform module — each one inspected by the security agent.

When the daemon is running it already holds those modules in memory, so the CLI
sends it the text over a per-user named pipe
(`\\.\pipe\press-daemon-v<PROTOCOL_VERSION>-<user>`, currently `v2`) and never
imports the transform module. The version is part of the name so that a CLI
from a newer install, whose command names or keywords changed, does not reach
an older running daemon — it finds no pipe and transforms in-process instead.

```
press halfwidth
   │
   ├─ PID file missing? ──────────────► transform in-process (unchanged)
   │
   └─ PID file present
        │  JSON request over named pipe (2 s deadline)
        ▼
   daemon: _pipe.handle_request → CommandDispatcher.transform
        │  JSON reply
        ▼
   stdout / clipboard
```

Measured on Windows 11 with an `open` audit hook:

| Command | Opens (delegated) | Opens (local) | Wall clock |
|---|---|---|---|
| `fix-encoding` | 55 | 155 | 100 ms vs 151 ms |
| `halfwidth` | 55 | 56 | ~unchanged |

Delegation flattens every command to the same bounded cost, and the heavier a
command's imports, the more it saves.

**Design constraints**, each load-bearing:

- **The gate must be cheaper than the pipe.** `ctypes` + `threading` cost 8 file
  opens; `pathlib` costs 20. So `try_delegate()` first `stat`s the daemon PID
  file and returns early when no daemon is listening, and `_pipe.py` re-derives
  that path without `pathlib`. A test pins the derivation to `press._paths` so
  the duplication cannot drift. Without this gate, delegation made the
  *no-daemon* path slower (54 → 61 opens) on exactly the machines it targets.
- **Fallback is always available.** No daemon, a stale PID file, a wedged daemon
  (2 s deadline), or a malformed reply all fall back to the in-process
  transform. `PRESS_NO_DAEMON=1` opts out entirely.
- **CLI flags win over daemon config.** Options travel with the request;
  `CommandDispatcher.transform(..., kwargs=...)` uses them instead of the
  daemon's `daemon_kwargs` config defaults (which serve the hotkey path).
- **Only registry transforms are reachable.** The server resolves the name
  with `resolve_spec()`, so anything that is not a simple or parametric
  transform (`hold`, `clear`, `dict`, `type`, …) is rejected as an unknown
  command, and so is any option not declared in that command's `cli_args`.

**Pipe security**, hardened against local pipe-squatting (a rogue process
claiming the pipe name to harvest clipboard text):

- **Owner-only DACL.** The pipe is created with an explicit SDDL descriptor
  (`D:P(A;;GA;;;OW)`) that grants access only to the account that started the
  daemon. Windows' *default* named-pipe descriptor grants read access to
  `Everyone` and the anonymous account, which would let any local user read a
  delegated request; the owner-only DACL removes that.
- **First-instance ownership.** The server's first `CreateNamedPipeW` sets
  `FILE_FLAG_FIRST_PIPE_INSTANCE`, so it fails with `ERROR_ACCESS_DENIED` (and
  logs, then disables delegation) if another process already owns the name
  instead of silently becoming a second server.
- **Server identity check (client side).** Before sending any text,
  `try_delegate()` calls `GetNamedPipeServerProcessId` and compares it to the
  PID in the daemon's PID file; on mismatch it falls back to the in-process
  transform. This is the client's defence against a squatter that won the name
  before the daemon started.
- **No token impersonation.** The client opens the pipe with
  `SECURITY_SQOS_PRESENT` at anonymous impersonation level, so a malicious
  server cannot `ImpersonateNamedPipeClient` to borrow the caller's token.
- **Remote clients rejected** via `PIPE_REJECT_REMOTE_CLIENTS`.

## Clipboard stash, hold and undo

Three features with different jobs, deliberately under different names:

| Feature | Front end | Storage | Code |
|---------|-----------|---------|------|
| Stash — save now, restore later | CLI `press stash push/pop/drop/list` | File: `%APPDATA%\press\stash.txt` (DPAPI) | `transforms/stash.py`, `_cli_stash.py` |
| Hold — block overwrites until released | Daemon hotkey `h`,`o` (toggle) | In-memory: `clipboard.ClipboardGuard` | `_toggle_hold()` in `daemon/_dispatch.py` |
| Undo — swap back what press overwrote | CLI `press undo`; daemon `Shift+Z` | CLI: `%APPDATA%\press\undo.txt` (DPAPI); daemon: in-memory `_undo_text` | `transforms/undo.py`, `_snapshot_clipboard_for_undo()` / `_remember_for_undo()` |

Only the hold turns the tray icon red. The stash survives process restarts and
keeps one slot (`push` refuses to replace it); its file format, shared with
`undo.txt`, records whether the text carried the sensitive-exclusion formats so
`pop` can restore them.

Undo is dual-layer like hold: each front end keeps its own slot. Both ask
`transforms.undo.snapshot_allowed()` before keeping a copy — it refuses when
the clipboard carries the sensitive-exclusion formats or `PRESS_NO_UNDO=1` is
set — and any new code path that overwrites the clipboard must take the
snapshot first. Snapshots are best-effort and never fail the transform.

`ClipboardGuard` has two layers: a hidden window restores the held text on
`WM_CLIPBOARDUPDATE`, and a `WH_KEYBOARD_LL` hook re-asserts it on `Ctrl+V` /
`Shift+Insert`. The guard recognises its own writes by clipboard owner
(`GetClipboardOwner()` is its window), never by a flag, and stands down on the
15th restore within 3 s (`_STORM_LIMIT` / `_STORM_WINDOW`: another tool is
fighting it).

## Performance characteristics

Measured on Windows 11, Python 3.13, direct `uv run` invocation.

### Startup time

| Component | Cost | Notes |
|-----------|------|-------|
| `uv run` process spawn | ~150 ms | Irreducible; use PyInstaller `--onedir` build to eliminate |
| Python interpreter | ~40 ms | Irreducible |
| `argcomplete` import | ~13 ms | Only when the shell-completion hook calls press (`_ARGCOMPLETE` set); skipped on a normal run |
| `press` package code | ~7 ms | Dominated by `argparse` + `commands` setup |
| Any single transform module | 0.4–5 ms | Loaded lazily on first use |
| `charset_normalizer` (encoding_repair) | ~63 ms | Lazy-loaded; only paid when `fix-encoding` is invoked |

The `transforms/__init__.py` PEP 562 `__getattr__` caches each symbol after first access,
so repeated calls within one process cost < 0.1 µs.

With a daemon running, the transform module import disappears from the CLI's
cost entirely — see [Daemon delegation](#daemon-delegation-named-pipe).
`test/perf/test_startup.py` enforces the file-open budget in CI.

### Transform throughput

All figures are for 1 000 calls; typical clipboard input is 1–20 lines (< 1 ms for all transforms).

| Transform | Input | Time / 1 000 calls |
|-----------|-------|-------------------|
| `to_snake_case` / `to_camel_case` | 3 000 lines | 5.4 ms |
| `sort_lines` | 3 000 lines | 1.6 ms |
| `dedupe_lines` | 3 000 lines | 0.3 ms |
| `trim_lines` | 3 000 lines | 0.15 ms |
| `collapse_whitespace` | 100 lines | 0.054 ms |
| `to_crlf` | 100 lines | 0.014 ms |
| `base64_encode` / `json_format` | 100 lines | < 0.01 ms |

`case.py` uses module-level compiled regex patterns (`_RE_UPPER_SEQ`, `_RE_LOWER_UPPER`,
`_RE_SPLIT`) — pre-compilation gives a 1.4× speedup over inline `re.sub(pattern_str, ...)`.

## Directory layout

```
press/
├── __init__.py
├── __main__.py          CLI entry point, top-level argparse, transform registration
├── _cli_helpers.py      Shared CLI I/O helpers (read/write, -C undo snapshot)
├── _cli_catalog.py      Unknown-command listing (error path only)
├── _cli_chain.py        `chain` command
├── _cli_config.py       `config` command group
├── _cli_daemon.py       `daemon` command group
├── _cli_dict.py         `dict` command group
├── _cli_notify.py       `notify` command group
├── _cli_stash.py        `stash` command group
├── _cli_trace.py        `trace` command group
├── commands.py          Command registry (simple / parametric / special)
├── clipboard.py         Win32 ctypes clipboard API + ClipboardGuard
├── keystrokes.py        Win32 SendInput synthesis (the `type` command)
├── config.py            TOML → PressConfig dataclass (_SECTIONS registry)
├── dictionary.py        TSV dictionary CRUD + configured_dict_path()
├── genpass.py           Password generator (secrets)
├── _dpapi.py            DPAPI protect/unprotect (stash.txt, undo.txt)
├── _notify.py           notify-off marker switch
├── _paths.py            %APPDATA%\press path helpers
├── _pipe.py             Named-pipe protocol + CLI client
├── _version.py          Installed version lookup (CLI + daemon)
├── daemon/              pystray + pynput daemon (Windows only)
│   ├── __init__.py      Public API re-exports
│   ├── _backends.py     pystray / pynput seam (Protocols)
│   ├── _tray.py         Tray icon image (Pillow)
│   ├── _hotkeys.py      Hotkeys, leader listener, worker thread
│   ├── _sequence.py     SequenceResolver, KeySuppression (pure rules)
│   ├── _dispatch.py     CommandDispatcher
│   ├── _notifications.py  Notification gate
│   ├── _lifecycle.py    Mutex, PID/status, start/stop/status
│   ├── _logs.py         Rotating log, trace level, daemon logs
│   ├── _pipe.py         Named-pipe server
│   └── _service.py      run_daemon
└── transforms/
    ├── __init__.py      PEP 562 lazy loader (built from the registry)
    ├── case.py          snake/camel/pascal/kebab, upper/lower/title/…
    ├── dictionary.py    TSV-based lookup (forward / reverse)
    ├── encode.py        Base64 / URL encode-decode
    ├── encoding_repair.py  Mojibake repair (charset-normalizer)
    ├── escape.py        unicode-escape / HTML entities
    ├── hashing.py       hashlib hex digest
    ├── json_fmt.py      JSON format / compact
    ├── kana.py          hiragana ↔ katakana (jaconv)
    ├── lineending.py    CRLF / LF / CR, strip-newlines, to_lf
    ├── lines.py         trim / dedupe / sort / number / reverse
    ├── replace.py       regex / fixed-string replace
    ├── separator.py     underscore ↔ hyphen, strip-commas, digits-only
    ├── slug.py          URL slug
    ├── sql.py           SQL IN clause generator
    ├── stash.py         One-slot stash file + shared slot-file format
    ├── stats.py         count report
    ├── table.py         TSV/CSV → Markdown table
    ├── timestamp.py     Unix time ↔ ISO 8601
    ├── undo.py          Undo snapshot + snapshot_allowed()
    ├── unicode_norm.py  NFC/NFD/NFKC/NFKD + check_norm
    ├── whitespace.py    collapse-whitespace
    └── width.py         full-width ↔ half-width, enlarge-kana (jaconv)

test/
├── conftest.py          Markers, windows_only auto-skip, shared fixtures
│                        (notifications_open, held_daemon_mutex)
├── unit/                One test_<module>.py per module (≈50 files), plus
│                        cross-cutting suites such as test_cli_catalog.py,
│                        test_daemon_trace_instrumentation.py and
│                        test_clipboard_win32.py (real Win32, windows_only)
└── perf/                Startup / file-open budget, transform throughput,
                         dictionary load (run by the normal pytest job)
```
