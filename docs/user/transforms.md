# Transforms Reference

All transforms read from **stdin** by default and write to **stdout**.
Use `-c` / `-C` for clipboard input / output.

## Common options

| Flag | Long form | Description |
|---|---|---|
| `-c` | `--clip-in` | Read input from clipboard |
| `-C` | `--clip-out` | Write output to clipboard (also prints to stdout) |
| `-v` | `--verbose` | Show before/after details on stderr |
| `-q` | `--quiet` | Suppress all stderr output |
| | `--fallback` | Return original text on failure (exit 0) |

## Width conversion

### `halfwidth` (`hw`)

Convert full-width characters to half-width.

```bash
echo "ＴＡＢＬＥ１　" | press halfwidth
# → TABLE1
```

### `fullwidth` (`fw`)

Convert half-width characters to full-width.

```bash
echo "TABLE1" | press fullwidth
# → ＴＡＢＬＥ１
```

## Whitespace

### `normalize` (`norm`)

Remove leading/trailing whitespace and blank lines. Trims each line individually.

```bash
printf "\n  USER_ID \t\r\n" | press normalize
# → USER_ID
```

## Line endings

### `crlf` / `lf` / `cr`

Unify all line endings to the specified style.

```bash
cat file.txt | press crlf   # → CRLF (\r\n)
cat file.txt | press lf     # → LF   (\n)
cat file.txt | press cr     # → CR   (\r)
```

## Separator conversion

### `hyphen` (`hy`)

Replace all underscores with hyphens.

```bash
echo "USER_ID" | press hyphen
# → USER-ID
```

### `underscore` (`us`)

Replace all hyphens with underscores.

```bash
echo "USER-ID" | press underscore
# → USER_ID
```

## SQL

### `sql-in` (`sq`)

Convert a newline-delimited list to a SQL `IN` clause.

```bash
printf "USER1\nUSER2\nUSER3" | press sql-in
# → 'USER1','USER2','USER3'
```

Options:

| Flag | Default | Description |
|---|---|---|
| `--quote` | `'` | Quote character |
| `--wrap` | off | Wrap result in parentheses: `('A','B')` |

## Unicode escape

### `unicode-decode` (`ud`)

Decode `\uXXXX` escape sequences to readable text.

```bash
echo '\u30c6\u30b9\u30c8' | press unicode-decode
# → テスト
```

On failure (invalid escape sequence):
- Default: write error to stderr, exit code 1
- With `--fallback`: return original text, exit code 0

### `unicode-encode` (`ue`)

Encode text to `\uXXXX` escape sequences.

```bash
echo "テスト" | press unicode-encode
# → \u30c6\u30b9\u30c8
```

## HTML

### `html-decode` (`hd`)

Decode HTML entities.

```bash
echo "&lt;div&gt;&amp;" | press html-decode
# → <div>&
```

## Clipboard utilities

### `clear` (`cl`)

Wipe the clipboard contents.

```bash
press clear
```

### `hold`

Protect clipboard from being overwritten. Toggle on/off.

```bash
press hold        # activate protection
# ... paste safely ...
press hold        # deactivate
```

See {doc}`daemon` for using `hold` via hotkey in the background daemon.

## Dictionary lookup

### `dict`

Look up clipboard text in a custom TSV dictionary.

```bash
press dict -c -C            # forward: FOOBER01 → TABLE_HOGEHOGE
press dict -r -c -C         # reverse: TABLE_HOGEHOGE → FOOBER01
press dict --file custom.tsv -c -C
```

See {doc}`dictionary` for dictionary file format and management.

## Character encoding

### `fix-encoding`

Detect and fix mojibake (garbled text due to wrong encoding interpretation).

```bash
# Paste garbled Shift_JIS text and fix it
press fix-encoding -c -C
```
