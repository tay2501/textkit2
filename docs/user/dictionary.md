# Custom Dictionary

Use a TSV dictionary when there is **no pattern** between source and target names
(e.g. system codes vs. document names).

## File format

```
# Lines starting with # are comments
# Format: SOURCE<TAB>TARGET

FOOBER01	TABLE_HOGEHOGE
FOOBER02	TABLE_FUGAFUGA
USER-ID	USER_ID
```

- Encoding: **UTF-8** (no BOM)
- Separator: **tab** (`\t`)
- Column 3 and beyond are ignored
- Empty lines are ignored

## Default location

```
%APPDATA%\press\dict\default.tsv
```

Windows path: `C:\Users\<username>\AppData\Roaming\press\dict\default.tsv`

## Managing entries

```bash
press dict list                          # show all entries in default.tsv
press dict list --file ~/my.tsv          # show specific file
press dict add FOOBER01 TABLE_HOGEHOGE   # append entry to default.tsv
press dict remove FOOBER01               # remove entry from default.tsv
```

## Multiple dictionary files

List multiple files in `config.toml`. Files are searched **in order**; the first match wins.

```toml
[dictionary]
files = [
    "%APPDATA%/press/dict/project_a.tsv",
    "%APPDATA%/press/dict/common.tsv",
]
```

## Bidirectional lookup

By default, `press dict -r` performs reverse lookup (TARGET → SOURCE).

Disable reverse lookup:

```toml
[dictionary]
bidirectional = false
```

## Reloading

After editing a TSV file, reload without restarting the daemon:

```bash
press daemon restart
```

Or from the tray icon: right-click → **Reload dictionary**.
