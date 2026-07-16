# Hotkey Configuration

The `press` daemon registers a **prefix key** system similar to Emacs and nano.

**Two-step sequence:**
1. Press the **prefix chord** simultaneously (default: `Ctrl+Shift+0`)
2. Release all keys, then press a **single binding key**

## Default bindings

**Prefix chord:** `Ctrl+Shift+0` (simultaneous)

| Key after prefix | Transform | Example |
|---|---|---|
| `W` | halfwidth | `ＴＡＢＬＥ１` → `TABLE1` |
| `F` | fullwidth | `TABLE1` → `ＴＡＢＬＥ１` |
| `N` | normalize | `  USER_ID  ` → `USER_ID` |
| `C` | crlf | line endings → CRLF |
| `L` | lf | line endings → LF |
| `R` | cr | line endings → CR |
| `U` | hyphen | `USER_ID` → `USER-ID` |
| `Shift+U` | underscore | `USER-ID` → `USER_ID` |
| `S` | sql-in | `A\nB\nC` → `'A','B','C'` |
| `D` | dict (forward) | `FOOBER01` → `TABLE_HOGEHOGE` |
| `Shift+D` | dict (reverse) | `TABLE_HOGEHOGE` → `FOOBER01` |
| `E` | unicode-decode | `\u30c6...` → `テスト` |
| `Shift+E` | unicode-encode | `テスト` → `\u30c6...` |
| `H` | hold (toggle) | protect clipboard |
| `Z` | clear | wipe clipboard |
| `Shift+Z` | undo | restore the clipboard text the last hotkey transform overwrote |
| `K` | trim | `a␣␣\nb␣` → `a\nb` (see `[trim]` in {doc}`config`) |
| `O` | dedupe | `A\nB\nA` → `A\nB` |
| `P` | sort | `B\nA` → `A\nB` |
| `Esc` | cancel | dismiss prefix mode |

## Customizing hotkeys

Edit `%APPDATA%\press\config.toml`:

```toml
[hotkeys]
prefix = "ctrl+shift+0"   # change prefix key

[hotkeys.bindings]
W = "halfwidth"
"shift+w" = "fullwidth"     # reassign Shift+W
X = "sql-in"                # add custom binding
```

See {doc}`config` for the full configuration reference.

## Known limitations

- Hotkeys do not work when an **elevated (administrator) process** has focus
  (e.g. Task Manager, UAC dialogs). This is a Windows security restriction.
- The prefix key timeout is **2 seconds**. Press the second key within this window.
