# Configuration Reference

**Location:** `%APPDATA%\press\config.toml`

If the file does not exist, all defaults apply. No configuration is required to start using `press`.

Use `press config validate` to check the file and `press config reset` to restore defaults
(optionally per section with `--key hotkeys | sql_in | trim | dictionary | ui | hold | type | pipelines`).

## Full example

```toml
schema_version = 1

[hotkeys]
prefix = "ctrl+shift+0"

[hotkeys.bindings]
"shift+d" = "dict_reverse"
"shift+z" = "undo"

[sql_in]
quote_char = "'"
wrap       = false

[trim]
both = false

[dictionary]
files = ["%APPDATA%/press/dict/default.tsv"]

[ui]
startup_notification = true
hold_icon            = true
notify_level         = "off"

[hold]
monitor_clipboard    = true
intercept_paste_keys = true

[type]
max_chars      = 2000
chunk_size     = 200
chunk_delay_ms = 5
newline        = "enter"

[pipelines]
cleanup = ["trim", "dedupe", "lf"]
```

## Keys reference

### `[hotkeys]`

| Key | Type | Default | Description |
|---|---|---|---|
| `prefix` | string | `"ctrl+shift+0"` | Prefix key in pynput notation |

### `[hotkeys.bindings]`

Map a **single keystroke** after the prefix to a command name. Keys are
case-insensitive; use `"shift+x"` syntax for shifted keys. User-defined entries
are **merged with** the defaults — only specify what you want to add or change.

Bindings are optional. After the prefix you can always **type a command name or
alias** instead (`Ctrl+Shift+0`, then `t`, `m` runs trim, exactly like
`press tm`), so only two bindings ship by default: `shift+d` for `dict_reverse`
(no CLI name to type) and `shift+z` for `undo` (a panic key).

```{warning}
A **single-character** binding fires on the first keypress and therefore hides
every typed sequence starting with that letter — `k = "trim"` makes `kata`,
`kb`, and every other `k…` name unreachable. `shift+<key>` chords never
collide. `press config validate` reports the shadowing as a warning (the config
is still valid, and validation still exits 0).
```

See {doc}`hotkeys` for how sequences resolve.

### `[sql_in]`

Options applied when `sql-in` is dispatched via hotkey (the CLI uses its own flags).

| Key | Type | Default | Description |
|---|---|---|---|
| `quote_char` | string | `"'"` | Character used to quote each value |
| `wrap` | bool | `false` | Wrap result in `( )` |

### `[trim]`

Options applied when `trim` is dispatched via hotkey (the CLI uses `--both`).

| Key | Type | Default | Description |
|---|---|---|---|
| `both` | bool | `false` | `true`: strip leading whitespace too (like CLI `trim --both`); `false`: trailing only |

### `[dictionary]`

| Key | Type | Default | Description |
|---|---|---|---|
| `files` | list of strings | `["%APPDATA%/press/dict/default.tsv"]` | Dictionary files in priority order |

### `[ui]`

| Key | Type | Default | Description |
|---|---|---|---|
| `startup_notification` | bool | `true` | Show tray notification on daemon start |
| `hold_icon` | bool | `true` | Change tray icon when HOLD is active |
| `notify_level` | string | `"off"` | Tray notification verbosity: `"off"`, `"success"`, `"error"`, or `"all"` |

### `[hold]`

| Key | Type | Default | Description |
|---|---|---|---|
| `monitor_clipboard` | bool | `true` | Layer 1: watch `WM_CLIPBOARDUPDATE` and restore held text |
| `intercept_paste_keys` | bool | `true` | Layer 2: hook `Ctrl+V` / `Shift+Insert` while HOLD is active |

### `[type]`

Options for the `type` command, which pastes by synthesizing keystrokes
instead of by `Ctrl+V` (hotkey-only — see {doc}`hotkeys`).

| Key | Type | Default | Description |
|---|---|---|---|
| `max_chars` | int | `2000` | Refuse longer clipboards. Typing is visible and interruptible, so this is a guard rail |
| `chunk_size` | int | `200` | Key events per `SendInput` call. Lower it if a slow application drops characters |
| `chunk_delay_ms` | int | `5` | Pause between chunks, giving the target's message queue time to drain |
| `newline` | string | `"enter"` | What a line break becomes: `"enter"` an Enter press, `"unicode"` a literal `U+000A`, `"skip"` nothing |

```{note}
Set `newline = "unicode"` or `"skip"` if you mostly paste into a chat client —
with `"enter"`, a multi-line clipboard **sends** each line. An unrecognised
value falls back to `"enter"` rather than stopping the daemon.
```

### `[pipelines]`

Named transform chains. Each key maps a pipeline name to an ordered array of
registry command names or aliases. Run with `press chain <name>` or bind the
name to a hotkey in `[hotkeys.bindings]` like any built-in command.

| Rule | Behaviour |
|---|---|
| Steps | Must be transform commands or aliases (`dict`, `clear`, `hold` are not allowed) |
| Name collision | A pipeline cannot shadow a command name — the command wins; `press config validate` reports it |
| Nesting | A pipeline cannot reference another pipeline |
| Parametric steps | Run with defaults on the CLI; hotkey dispatch applies `[sql_in]` / `[trim]` config values |

```toml
[pipelines]
cleanup = ["trim", "dedupe", "lf"]

[hotkeys.bindings]
x = "cleanup"
```

> **Note — the same pipeline can behave differently by route.** A parametric
> step such as `trim` uses its *function defaults* when the pipeline runs from
> the CLI (`press chain cleanup`), but picks up your `[trim]` / `[sql_in]`
> config values when the pipeline runs from a **hotkey**. If you need a step to
> honour a specific option in both places, set it in the relevant config
> section and remember the CLI `chain` path ignores it. Per-step CLI flags
> inside a pipeline are not supported.
