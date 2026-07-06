# Configuration Reference

**Location:** `%APPDATA%\press\config.toml`

If the file does not exist, all defaults apply. No configuration is required to start using `press`.

Use `press config validate` to check the file and `press config reset` to restore defaults
(optionally per section with `--key hotkeys | sql_in | trim | dictionary | ui | hold`).

## Full example

```toml
schema_version = 1

[hotkeys]
prefix = "ctrl+shift+0"

[hotkeys.bindings]
w         = "halfwidth"
f         = "fullwidth"
n         = "normalize"
c         = "crlf"
l         = "lf"
r         = "cr"
u         = "hyphen"
"shift+u" = "underscore"
s         = "sql-in"
d         = "dict"
"shift+d" = "dict_reverse"
e         = "unicode-decode"
"shift+e" = "unicode-encode"
h         = "hold"
z         = "clear"
k         = "trim"
o         = "dedupe"
p         = "sort"

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
```

## Keys reference

### `[hotkeys]`

| Key | Type | Default | Description |
|---|---|---|---|
| `prefix` | string | `"ctrl+shift+0"` | Prefix key in pynput notation |

### `[hotkeys.bindings]`

Map a key (after the prefix) to a transform name. Keys are case-insensitive.
Use `"shift+x"` syntax for shifted keys. User-defined entries are **merged
with** the defaults — only specify the keys you want to change.

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
