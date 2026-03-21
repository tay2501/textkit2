# Quick Start

## 1. Install

```bash
uv tool install press
```

## 2. Try a transform

```bash
echo "ＴＡＢＬＥ１" | press halfwidth
# TABLE1

printf "USER1\nUSER2\nUSER3" | press sql-in
# 'USER1','USER2','USER3'
```

## 3. Use with clipboard

Copy any text to your clipboard, then:

```bash
press halfwidth -c -C     # transform clipboard in-place
```

## 4. Start the daemon

```bash
press daemon start
```

Now press **Ctrl+Shift+F10**, then **W** — your clipboard is transformed to half-width instantly, in any application.

See {doc}`hotkeys` for all default bindings.

## 5. Set up your dictionary

Create `%APPDATA%\press\dict\default.tsv`:

```
FOOBER01	TABLE_HOGEHOGE
FOOBER02	TABLE_FUGAFUGA
```

Then:

```bash
# Copy "FOOBER01" → press Prefix + D → clipboard becomes "TABLE_HOGEHOGE"
press daemon restart   # reload after editing
```

---

**Next:** {doc}`transforms` — complete transforms reference
