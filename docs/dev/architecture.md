# Architecture

## Overview

`press` has two independent entry points sharing the same transform core.

```
┌─────────────────────────────────────┐   ┌──────────────────────┐
│  press daemon                       │   │  press CLI            │
│  (long-running, Windows only)       │   │  (one-shot)           │
│                                     │   │                       │
│  HotkeyManager                      │   │  argparse             │
│    pynput GlobalHotKeys             │   │    ↓                  │
│    LeaderKeyListener                │   │  _run_transform()     │
│    ↓                                │   │    ↓                  │
│  _WorkerThread (queue)              │   │  stdout / clipboard   │
│    ↓                                │   └──────────────────────┘
│  CommandDispatcher                  │
│    ↓                                │
│  win32clipboard (clipboard.py)      │
│  pystray tray icon                  │
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
└─────────────────────────────────────┘
```

## Module responsibilities

| Module | Responsibility |
|--------|----------------|
| `__main__.py` | argparse construction, I/O wiring (`stdin`/`stdout`/clipboard), UTF-8 setup |
| `commands.py` | Declarative registry of all simple transform commands (`SimpleCommand` + `SIMPLE_COMMANDS` + `SIMPLE_COMMAND_INDEX`); single source of truth shared by CLI and daemon |
| `clipboard.py` | Win32 ctypes API — `get_clipboard_text`, `set_clipboard_text`, `clear_clipboard` (Windows only) |
| `config.py` | TOML loader → frozen `PressConfig` dataclass hierarchy (`slots=True`) |
| `daemon.py` | pystray tray icon, pynput global hotkey listener, leader-key state machine, in-memory HOLD state, singleton mutex — all Windows daemon logic in one module |
| `dictionary.py` | TSV file CRUD — `add_entry`, `remove_entry`, `list_entries` |
| `transforms/` | Pure `str → str` functions, one module per domain; no I/O or side effects |

## Key design decisions

| Decision | Rationale |
|---|---|
| `commands.py` central registry | Single source of truth for command→function mapping; CLI and daemon both derive from it, eliminating duplication |
| No DI framework | Function arguments are sufficient at this scale |
| No async | Win32 message loop handles event dispatch; asyncio adds no value |
| No ORM | TSV dictionary is an in-memory `dict` loaded on demand |
| `transforms/` are pure functions | No side effects = trivially testable in isolation |
| OS-specific code isolated | `clipboard.py` contains all Win32 ctypes calls; `daemon.py` contains all pystray/pynput calls |
| Flat package structure | Single `press/` package; no Polylith components/bases split |
| `tomllib` for config | Python 3.11+ standard library; no Pydantic needed |
| Lazy imports everywhere | PEP 562 `__getattr__` in `transforms/__init__.py`; deferred imports in `__main__.py` and `daemon.py` reduce startup time on HDD/EDR-monitored systems |
| PyInstaller `--onedir` | `--onefile` re-extracts on every run; `--onedir` is cached by EDR after first run |

## Command registration flow

Adding a **simple** command (signature `fn(text: str) -> str`, no extra CLI flags):

```
press/commands.py
  └── SIMPLE_COMMANDS: tuple[SimpleCommand, ...]
            │
     ┌──────┴──────┐
     │             │
__main__.py     daemon.py
_register_      CommandDispatcher
simple_command  ._transform()
  (loop)          (index lookup)
```

Adding a **parametric** command (needs extra CLI flags like `--indent`):

1. Write the transform function in `press/transforms/<domain>.py`
2. Add a `_register_<name>_command()` function in `__main__.py`
3. Add a `case "<name>":` branch in `CommandDispatcher._transform()` in `daemon.py`

## Prefix key state machine

```
[IDLE]
  │  prefix key pressed (default: Ctrl+Shift+F10)
  ▼
[WAITING]  ─── 2 s timeout ──→ [IDLE]
  │  binding key pressed (e.g. "w" → halfwidth)
  ▼
[EXECUTING] → transform clipboard in-place → [IDLE]
```

The `LeaderKeyListener` runs in a separate thread; results are enqueued for the
`_WorkerThread` so the OS hotkey callback returns immediately.

## Clipboard HOLD

Two independent hold implementations coexist:

| Context | Storage | Trigger |
|---------|---------|---------|
| CLI (`press hold`) | File: `%APPDATA%\press\hold` | `toggle_hold_file()` in `transforms/hold.py` |
| Daemon (hotkey `h`) | In-memory: `CommandDispatcher._held_text` | `_toggle_hold()` in `daemon.py` |

Both update the tray icon to red when holding. The file-based approach survives
process restarts; the in-memory approach is faster and needs no disk access.

## Directory layout

```
press/
├── __init__.py
├── __main__.py          CLI entry point, argparse, I/O dispatch
├── commands.py          Central command registry (SimpleCommand)
├── clipboard.py         Win32 ctypes clipboard API
├── config.py            TOML → PressConfig dataclass
├── daemon.py            pystray + pynput daemon (Windows only)
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
