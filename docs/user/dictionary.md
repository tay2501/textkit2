# Custom Dictionary

> **Applies to:** both — `press dict` on the CLI ({doc}`cli`) and
> `Ctrl+Shift+0`, then `d`,`i`,`c`,`t` / `Shift+D` (reverse) from the daemon.

Use a TSV dictionary when there is **no rule** linking source and target names
(system codes vs. document names, for example). Each input line is looked up
as an exact match.

## File format

```
# comment
FOOBER01	TABLE_HOGEHOGE
USER-ID	USER_ID
```

- `SOURCE<TAB>TARGET`; columns after the second, blank lines, and `#` lines are ignored.
- `press dict add` / `remove` always write **UTF-8 without BOM, CRLF**.
- Hand-edited files are read leniently: a UTF-8 BOM (Notepad, Excel) is
  stripped and LF endings are accepted. Shift_JIS and UTF-16 are **not**
  supported — re-save as UTF-8.

## Which file is used

| Front end | File |
|---|---|
| CLI | `--file PATH`, else `%APPDATA%\press\dict\default.tsv` (`~/.config/press/dict/default.tsv` off Windows) |
| Daemon | The **first** entry of `[dictionary] files` in `config.toml` (default: the same `default.tsv`) |

The daemon re-reads the file on every lookup, so edits apply immediately.

## Managing entries

```bash
press dict list                          # all entries
press dict add FOOBER01 TABLE_HOGEHOGE   # add
press dict remove FOOBER01               # remove (alias: rm)
press dict list --file ~/my.tsv          # any command accepts --file
```

## Reverse lookup

`press dict -r` (CLI) and `Shift+D` (daemon) look up TARGET → SOURCE.
