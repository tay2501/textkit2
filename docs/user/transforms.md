# Transforms Reference

> **Applies to:** CLI **and** daemon. Every command below runs as
> `press <name>` and as `Ctrl+Shift+0`, then the name (see {doc}`hotkeys`).
> From a hotkey, options come from `config.toml` (`[sql_in]`, `[trim]`) or the
> defaults; CLI flags are shown in the *Options* column. Input/output flags
> (`-c`, `-C`, …) are described in {doc}`cli`.

## Width & kana

| Command | Alias | Example |
|---|---|---|
| `halfwidth` | `hw` | `ＴＡＢＬＥ１` → `TABLE1` |
| `fullwidth` | `fw` | `TABLE1` → `ＴＡＢＬＥ１` |
| `enlarge-kana` | `ek` | `ぁァっ` → `あアつ` |
| `katakana` | `kata` | `ひらがな` → `ヒラガナ` |
| `hiragana` | `hira` | `カタカナ` → `かたかな` |

## Whitespace & line endings

| Command | Alias | Options | Effect |
|---|---|---|---|
| `normalize` | `norm` | | Strip each line and drop blank lines (`  USER_ID \t` → `USER_ID`) |
| `trim` | `tm` | `-b`/`--both` | Strip trailing whitespace per line (all Unicode spaces, incl. U+3000); `--both` strips leading too |
| `crlf` / `lf` / `cr` | | | Unify every line ending to `\r\n` / `\n` / `\r` |
| `strip-newlines` | `nn` | | Delete every line ending, insert nothing (`研究\n開発` → `研究開発`) |

```{note}
`strip-newlines` runs Latin words together (`hello\nworld` → `helloworld`) by
design. For a space instead, replace the breaks: `press replace -p '\r?\n' -r ' '`.
```

## Line operations

| Command | Alias | Options | Effect |
|---|---|---|---|
| `sort` | `st` | `-r`, `-n`/`--numeric`, `-i`/`--ignore-case` | Locale-aware sort (`locale.strcoll`); `--numeric` puts non-numbers last |
| `dedupe` | `dq` | `-i`/`--ignore-case`, `-a`/`--adjacent` | Drop duplicate lines, keep first occurrence and order; NFC-equivalent lines count as equal; `--adjacent` = `uniq` |
| `reverse-lines` | `rl` | | Reverse line order |
| `number-lines` | `nl` | `--start N`, `--sep SEP` | Prefix line numbers (default: from 1, TAB-separated) |

## Separators & case

| Command | Alias | Example |
|---|---|---|
| `hyphen` | `hy` | `USER_ID` → `USER-ID` |
| `underscore` | `us`, `underbar`, `ub` | `USER-ID` → `USER_ID` |
| `strip-commas` | `sc` | `1,234，567` → `1234567` (ASCII and full-width commas) |
| `digits-only` | `dg` | `TEL: 03-1234-5678` → `0312345678` (full-width digits kept) |
| `snake` / `camel` / `pascal` / `kebab` | `sn` / `cm` / `pc` / `kb` | `myVariable` ↔ `my_variable` ↔ `MyVariable` ↔ `my-variable` |
| `upper` / `lower` | `up` / `lo` | `Hello` → `HELLO` / `hello` |
| `title` | `tt` | `they're here` → `They're Here` |
| `capitalize` | `cap` | First letter of each **line** up, rest down (`hELLO` → `Hello`) |
| `swapcase` | `sw` | `Hello` → `hELLO` |

## Encoding & escapes

| Command | Alias | Example |
|---|---|---|
| `base64-encode` / `base64-decode` | `be` / `bd` | `Hello` ↔ `SGVsbG8=` |
| `url-encode` / `url-decode` | `urle` / `urld` | `a b&c` ↔ `a%20b%26c` |
| `unicode-encode` / `unicode-decode` | `ue` / `ud` | `テスト` ↔ `テスト` |
| `html-encode` / `html-decode` | `he` / `hd` | `<div>&` ↔ `&lt;div&gt;&amp;` |
| `fix-encoding` | `fe` | Repair mojibake by re-detecting the original encoding (`--threshold N`) |

A decode that fails (invalid input) exits 1 with an error; add `--fallback` to
output the input unchanged instead.

## Unicode normalization

| Command | Alias | Use |
|---|---|---|
| `nfc` | | Compose — fixes macOS (NFD) file names pasted on Windows |
| `nfd` | | Decompose into base + combining marks |
| `nfkc` | | Compatibility compose — folds full-width letters, ligatures (`ＡＢ ﬁ` → `AB fi`) |
| `nfkd` | | Compatibility decompose |
| `check-norm` | `cn` | Report `yes`/`no` per form without changing the text |

## SQL, JSON & tables

| Command | Alias | Options | Effect |
|---|---|---|---|
| `sql-in` | `sq` | `--quote-char C`, `--wrap` | Lines → `'A','B','C'` (`--wrap` adds `( )`) |
| `json-format` | `jf` | `--indent N` (default 2) | Pretty-print JSON |
| `json-compress` | `jc` | | JSON on one line |
| `markdown-table` | `mdt` | | TSV (Excel clipboard) or CSV → Markdown table; first row is the header |

## Text utilities

| Command | Alias | Options | Effect |
|---|---|---|---|
| `replace` | `rp` | `-p REGEX`, `-r REPL`, `-i`, `-F`/`--fixed` | Regex replace (`\1` refs); empty `-r` deletes matches; `-F` = literal |
| `hash` | `hs` | `-a`/`--algo NAME` | Hex digest of the UTF-8 bytes as-is (default `sha256`; any `hashlib` name) |
| `count` | `wc` | | chars, non-space, words, lines, UTF-8 bytes (`non-space` suits Japanese manuscripts) |
| `slug` | `sl` | `--unicode` | `Hello, World! Café` → `hello-world-cafe`; `--unicode` keeps Japanese |
| `unix-to-date` | `u2d` | `--utc` | Unix time per line (s/ms auto-detected) → ISO 8601, local time by default |
| `date-to-unix` | `d2u` | `--ms` | ISO 8601 per line → Unix seconds; no offset = local time |

```bash
echo "2026-07-17" | press replace -p '(\d+)-(\d+)-(\d+)' -r '\3/\2/\1'   # → 17/07/2026
printf "abc" | press hash --algo md5         # → 900150983cd24fb0d6963f7d28e17f72
echo "1752710400" | press unix-to-date --utc # → 2025-07-17T00:00:00+00:00
```
