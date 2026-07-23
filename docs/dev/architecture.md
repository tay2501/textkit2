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
│  (SIMPLE_COMMANDS registry)         │
└─────────────────────────────────────┘
              ↓ shared
┌─────────────────────────────────────┐
│  press/transforms/                  │
│  (pure functions, no I/O)           │
│                                     │
│  width.py      whitespace.py        │
│  lineending.py separator.py         │
│  sql.py        escape.py            │
│  case.py       encode.py            │
│  json_fmt.py   dictionary.py        │
│  encoding_repair.py  hold.py        │
│  lines.py                           │
└─────────────────────────────────────┘
```

When the daemon is running, the CLI offers each transform to it over a named
pipe instead of importing the transform module — see
[Daemon delegation](#daemon-delegation-named-pipe).

## Module responsibilities

| Module | Responsibility |
|--------|----------------|
| `__main__.py` | argparse construction, I/O wiring (`stdin`/`stdout`/clipboard), UTF-8 setup |
| `commands.py` | Declarative registry of all simple transform commands (`SimpleCommand` + `SIMPLE_COMMANDS` + `SIMPLE_COMMAND_INDEX`); single source of truth shared by CLI and daemon |
| `clipboard.py` | Win32 ctypes API — `get_clipboard_text`, `set_clipboard_text`, `clear_clipboard` (Windows only) |
| `config.py` | TOML loader → frozen `PressConfig` dataclass hierarchy (`slots=True`) |
| `_paths.py` | Single source for `%APPDATA%\press` locations |
| `_pipe.py` | Named-pipe protocol + CLI client (`try_delegate`); deliberately import-light |
| `daemon/` | Windows daemon package (see below); public API is `run_daemon`, `stop_daemon`, `daemon_status`, `daemon_logs` |
| `dictionary.py` | TSV file CRUD — `add_entry`, `remove_entry`, `list_entries` |
| `transforms/` | Pure `str → str` functions, one module per domain; no I/O or side effects |
| `transforms/lines.py` | Line-oriented operations: `trim_lines`, `dedupe_lines`, `sort_lines` |
| `transforms/unicode_norm.py` | Unicode normalization: `to_nfc`, `to_nfd`, `to_nfkc`, `to_nfkd`, `check_norm` |

### The `daemon/` package

| Module | Responsibility |
|--------|----------------|
| `_backends.py` | **The only importer of pystray and pynput**, behind `TrayIcon` / `KeyListener` Protocols |
| `_tray.py` | Tray icon image generation (Pillow) |
| `_hotkeys.py` | Prefix hotkey, leader-key listener lifecycle, `_WorkerThread` |
| `_sequence.py` | `SequenceResolver` — **pure** typed-sequence rules (stdlib only, no threads) |
| `_dispatch.py` | `CommandDispatcher` — clipboard transforms and notifications |
| `_lifecycle.py` | Singleton mutex, PID/status files, `stop_daemon`, `daemon_status` |
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
| OS-specific code isolated | `clipboard.py` holds the clipboard Win32 calls; `daemon/_backends.py` holds every pystray/pynput call |
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

## Prefix key state machine

```
[IDLE]
  │  prefix chord pressed simultaneously (default: Ctrl+Shift+0)
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

The listener runs with pynput's `suppress=True` so typed characters do not leak
into the focused window — which also means they are consumed rather than
delivered. Because every keystroke re-arms the inactivity timeout, a second,
non-re-armable `_LEADER_HARD_LIMIT` bounds how long press can hold the keyboard
at all; it is a safety valve, not part of the interaction.

Results are enqueued for the `_WorkerThread` so the OS hotkey callback returns
immediately.

## Daemon delegation (named pipe)

On EDR/DLP-monitored machines, `press <cmd>` is dominated not by the transform
(≤2 ms) but by the file opens the interpreter makes while importing the
transform module — each one inspected by the security agent.

When the daemon is running it already holds those modules in memory, so the CLI
sends it the text over a per-user named pipe (`\\.\pipe\press-daemon-v1-<user>`)
and never imports the transform module.

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
- **Only registry transforms are reachable.** The server rejects `hold`,
  `clear`, and `dict`, and rejects any option not declared in that command's
  `cli_args`.

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

## Clipboard HOLD

Two independent hold implementations coexist:

| Context | Storage | Trigger |
|---------|---------|---------|
| CLI (`press hold`) | File: `%APPDATA%\press\hold` | `toggle_hold_file()` in `transforms/hold.py` |
| Daemon (hotkey `h`) | In-memory: `ClipboardGuard` | `_toggle_hold()` in `daemon/_dispatch.py` |

Both update the tray icon to red when holding. The file-based approach survives
process restarts; the in-memory approach is faster and needs no disk access.

## Performance characteristics

Measured on Windows 11, Python 3.13, direct `uv run` invocation.

### Startup time

| Component | Cost | Notes |
|-----------|------|-------|
| `uv run` process spawn | ~150 ms | Irreducible; use PyInstaller `--onedir` build to eliminate |
| Python interpreter | ~40 ms | Irreducible |
| `argcomplete` import | ~13 ms | Required for tab completion |
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
| `normalize_whitespace` | 100 lines | 0.054 ms |
| `to_crlf` | 100 lines | 0.014 ms |
| `base64_encode` / `json_format` | 100 lines | < 0.01 ms |

`case.py` uses module-level compiled regex patterns (`_RE_UPPER_SEQ`, `_RE_LOWER_UPPER`,
`_RE_SPLIT`) — pre-compilation gives a 1.4× speedup over inline `re.sub(pattern_str, ...)`.

## Directory layout

```
press/
├── __init__.py
├── __main__.py          CLI entry point, argparse, I/O dispatch
├── commands.py          Central command registry (SimpleCommand)
├── clipboard.py         Win32 ctypes clipboard API
├── config.py            TOML → PressConfig dataclass
├── _paths.py            %APPDATA%\press path helpers
├── _pipe.py             Named-pipe protocol + CLI client
├── daemon/              pystray + pynput daemon (Windows only)
│   ├── __init__.py      Public API re-exports
│   ├── _backends.py     pystray / pynput seam (Protocols)
│   ├── _tray.py         Tray icon image (Pillow)
│   ├── _hotkeys.py      Hotkeys, leader listener, worker thread
│   ├── _sequence.py     SequenceResolver (pure typed-sequence rules)
│   ├── _dispatch.py     CommandDispatcher
│   ├── _lifecycle.py    Mutex, PID/status, stop/status
│   ├── _logs.py         Rotating log, daemon logs
│   ├── _pipe.py         Named-pipe server
│   └── _service.py      run_daemon
├── dictionary.py        TSV dictionary CRUD
└── transforms/
    ├── __init__.py      PEP 562 lazy loader
    ├── case.py          snake/camel/pascal/kebab
    ├── dictionary.py    TSV-based find/replace
    ├── encode.py        base64 / URL encode-decode
    ├── encoding_repair.py  mojibake repair (charset-normalizer)
    ├── escape.py        unicode-escape / HTML entities
    ├── hold.py          file-based HOLD toggle
    ├── json_fmt.py      JSON format / compress
    ├── lineending.py    CRLF / LF / CR conversion
    ├── separator.py     underscore ↔ hyphen
    ├── sql.py           SQL IN clause generator
    ├── unicode_norm.py  NFC/NFD/NFKC/NFKD normalization + check_norm
    ├── whitespace.py    whitespace normalisation
    └── width.py         full-width ↔ half-width (jaconv)

test/
├── conftest.py          pytest markers + auto-skip for windows_only
└── unit/
    ├── test_case.py
    ├── test_cli.py
    ├── test_clipboard_utils.py
    ├── test_config.py
    ├── test_daemon.py
    ├── test_dictionary_mgmt.py
    ├── test_dictionary_transforms.py
    ├── test_encode.py
    ├── test_encoding_repair.py
    ├── test_escape.py
    ├── test_hold.py
    ├── test_json_fmt.py
    ├── test_lineending.py
    ├── test_separator.py
    ├── test_sql.py
    ├── test_transforms_init.py
    ├── test_whitespace.py
    └── test_width.py
```
