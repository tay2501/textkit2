# Architecture

## Overview

`press` has two independent entry points sharing the same transform core.

```
┌─────────────────────────────────┐   ┌──────────────────┐
│  press daemon                   │   │  press CLI        │
│                                 │   │  (one-shot)       │
│  pynput Listener                │   │                   │
│     ↓ prefix key state machine  │   │  argparse         │
│  HotkeyDispatcher               │   │     ↓             │
│     ↓                           │   │  TransformExecutor│
│  TransformExecutor              │   │     ↓             │
│     ↓                           │   │  stdout           │
│  win32clipboard                 │   └──────────────────┘
│  pystray tray icon              │
└─────────────────────────────────┘
           ↓ shared
┌─────────────────────────────────┐
│  press/transforms/              │
│  (pure functions, no I/O)       │
│                                 │
│  width.py   whitespace.py       │
│  lineending.py  separator.py    │
│  sql.py     escape.py           │
│  encoding.py                    │
└─────────────────────────────────┘
```

## Key design decisions

| Decision | Rationale |
|---|---|
| No DI framework | Function arguments are sufficient at this scale |
| No async | Win32 message loop handles event dispatch; asyncio adds no value |
| No ORM | TSV dictionary is an in-memory `dict` loaded at startup |
| `transforms/` are pure functions | No side effects = trivially testable |
| OS-specific code isolated | `clipboard.py`, `hotkeys.py` contain all Win32 / pynput calls |
| Flat package structure | No Polylith components/bases split; single `press/` package |
| `tomllib` for config | Python 3.11+ standard library; no Pydantic needed |
| Lazy imports everywhere | Reduces startup time and memory on low-spec hardware |

## Prefix key state machine

```
[IDLE]
  │  prefix key pressed
  ▼
[WAITING]  ─── 2 s timeout ──→ [IDLE]
  │  second key pressed
  ▼
[EXECUTING] → transform clipboard → [IDLE]
  │  prefix key pressed again (cancel)
  ▼
[IDLE]
```

## Clipboard HOLD

The HOLD feature uses `WM_CLIPBOARDUPDATE` (event-driven, ~0% CPU).
A full `OpenClipboard()` lock is intentionally avoided because it causes
other applications to appear frozen.

## Directory layout

```
press/
├── press/
│   ├── __init__.py
│   ├── daemon.py          main loop: tray + hotkeys
│   ├── tray.py            pystray wrapper
│   ├── hotkeys.py         pynput Listener + state machine
│   ├── clipboard.py       win32clipboard + HOLD
│   ├── config.py          tomllib loader
│   ├── dictionary.py      TSV loader + lookup
│   └── transforms/
│       ├── __init__.py    public API
│       ├── width.py
│       ├── whitespace.py
│       ├── lineending.py
│       ├── separator.py
│       ├── sql.py
│       ├── escape.py
│       └── encoding.py
└── test/
    ├── test_transforms.py
    ├── test_dictionary.py
    └── test_config.py
```
