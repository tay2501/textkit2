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

## Line operations

### `trim` (`tm`)

Strip trailing whitespace from each line. Handles all Unicode whitespace
characters (`\t`, `\r`, U+3000, U+00A0, etc.) via `str.rstrip()`.

```bash
printf "hello   \nworld\t" | press trim
# → hello
# → world
```

Options:

| Flag | Description |
|---|---|
| `--both` / `-b` | Strip leading **and** trailing whitespace (`str.strip()`) |

```bash
printf "  hello  \n  world  " | press trim --both
# → hello
# → world
```

### `dedupe` (`dq`)

Remove duplicate lines, preserving the first occurrence and original order.
Comparison uses NFC Unicode normalisation so canonically equivalent forms
(e.g. precomposed vs decomposed accents) are treated as identical.

```bash
printf "apple\nbanana\napple\ncherry" | press dedupe
# → apple
# → banana
# → cherry
```

Options:

| Flag | Description |
|---|---|
| `--ignore-case` / `-i` | Case-insensitive comparison (original case preserved) |
| `--adjacent` / `-a` | Remove only adjacent duplicates (GNU `uniq` default behaviour) |

```bash
printf "Hello\nhello\nHELLO" | press dedupe --ignore-case
# → Hello

printf "a\na\nb\na" | press dedupe --adjacent
# → a
# → b
# → a
```

### `sort` (`st`)

Sort lines using locale-aware collation (`locale.strcoll`), matching
GNU `sort` default behaviour. Trailing newline is preserved.

```bash
printf "banana\napple\ncherry" | press sort
# → apple
# → banana
# → cherry
```

Options:

| Flag | Description |
|---|---|
| `--reverse` / `-r` | Reverse sort order |
| `--numeric` / `-n` | Numeric sort; non-numeric lines are placed last |
| `--ignore-case` / `-i` | Case-insensitive sort |

```bash
printf "10\n2\n1\n20" | press sort --numeric
# → 1
# → 2
# → 10
# → 20

printf "cherry\nApple\nbanana" | press sort --ignore-case
# → Apple
# → banana
# → cherry
```

## Character encoding

### `fix-encoding`

Detect and fix mojibake (garbled text due to wrong encoding interpretation).

```bash
# Paste garbled Shift_JIS text and fix it
press fix-encoding -c -C
```
