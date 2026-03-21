# Configuration Reference

**Location:** `%APPDATA%\press\config.toml`

If the file does not exist, all defaults apply. No configuration is required to start using `press`.

## Full example

```toml
[hotkeys]
prefix = "ctrl+shift+f10"

[hotkeys.bindings]
W         = "halfwidth"
F         = "fullwidth"
N         = "normalize"
C         = "crlf"
L         = "lf"
R         = "cr"
U         = "hyphen"
"shift+u" = "underscore"
S         = "sql-in"
D         = "dict"
"shift+d" = "dict_reverse"
E         = "unicode-decode"
"shift+e" = "unicode-encode"
H         = "hold"
Z         = "clear"

[sql_in]
quote_char = "'"
wrap       = false

[dictionary]
files          = ["%APPDATA%/press/dict/default.tsv"]
bidirectional  = true
case_sensitive = true

[encoding]
confidence_threshold = 0.7

[ui]
startup_notification = true
hold_icon            = true
```

## Keys reference

### `[hotkeys]`

| Key | Type | Default | Description |
|---|---|---|---|
| `prefix` | string | `"ctrl+shift+f10"` | Prefix key in pynput notation |

### `[hotkeys.bindings]`

Map a key (after the prefix) to a transform name. Keys are case-insensitive.
Use `"shift+x"` syntax for shifted keys.

### `[sql_in]`

| Key | Type | Default | Description |
|---|---|---|---|
| `quote_char` | string | `"'"` | Character used to quote each value |
| `wrap` | bool | `false` | Wrap result in `( )` |

### `[dictionary]`

| Key | Type | Default | Description |
|---|---|---|---|
| `files` | list of strings | `["%APPDATA%/press/dict/default.tsv"]` | Dictionary files in priority order |
| `bidirectional` | bool | `true` | Enable reverse lookup with `-r` |
| `case_sensitive` | bool | `true` | Case-sensitive key matching |

### `[encoding]`

| Key | Type | Default | Description |
|---|---|---|---|
| `confidence_threshold` | float | `0.7` | Minimum charset-normalizer confidence to apply fix |

### `[ui]`

| Key | Type | Default | Description |
|---|---|---|---|
| `startup_notification` | bool | `true` | Show tray notification on daemon start |
| `hold_icon` | bool | `true` | Change tray icon when HOLD is active |
