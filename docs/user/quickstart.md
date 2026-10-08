# Quick Start

> **Applies to:** both — step 2 is the CLI, step 3 the daemon.

## 1. Install

See {doc}`install` (release `.exe`, or `uv tool install '.[daemon]'` from a clone).

## 2. CLI — transform from a terminal

```bash
echo "ＴＡＢＬＥ１" | press halfwidth      # → TABLE1
printf "U1\nU2\nU3" | press sql-in        # → 'U1','U2','U3'
press halfwidth -C                        # transform the clipboard in place
press undo                                # changed your mind
```

More: {doc}`cli` and {doc}`transforms`.

## 3. Daemon — transform from any application

```bash
press daemon start
```

Copy some text, press **Ctrl+Shift+0** together, release, then type
**`h`,`a`,`l`** — `halfwidth` runs on the clipboard. Paste with `Ctrl+V`.

Any command name or alias the CLI accepts works the same way. More:
{doc}`daemon` and {doc}`hotkeys`.

## 4. Optional — a dictionary

Create `%APPDATA%\press\dict\default.tsv` (tab-separated):

```
FOOBER01	TABLE_HOGEHOGE
```

Then `press dict -C` (CLI) or `Ctrl+Shift+0`, then `Shift+D` for the reverse
lookup (daemon). See {doc}`dictionary`.
