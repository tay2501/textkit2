# Transforms Reference

> **Applies to:** CLI **and** daemon. Every command below runs as
> `press <name>` and as `Ctrl+Alt+K`, then the name (see {doc}`hotkeys`).
> From a hotkey, options come from `config.toml` (`[sql_in]`, `[trim]`) or the
> defaults; CLI flags are shown in the *Options* column. Input/output flags
> (`-C`/`--copy`, `--from-clipboard`, …) are described in {doc}`cli`. Flags
> borrow the spelling of the tool that does the same job (GNU coreutils,
> grep/ripgrep, jq), so `sort -n` means what it means in GNU sort.

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
| `collapse-whitespace` | | | Collapse runs of spaces/tabs (and U+3000) to one space, strip each line, drop blank lines (`  USER   ID \t` → `USER ID`) |
| `trim` | `tm` | `-t`/`--trailing` | Strip leading and trailing whitespace per line (all Unicode spaces, incl. U+3000); `--trailing` strips the end only, keeping indentation |
| `crlf` / `lf` / `cr` | | | Unify every line ending to `\r\n` / `\n` / `\r` |
| `strip-newlines` | `nn` | | Delete every line ending, insert nothing (`研究\n開発` → `研究開発`) |

```{note}
`strip-newlines` runs Latin words together (`hello\nworld` → `helloworld`) by
design. For a space instead, replace the breaks: `press replace -e '\r?\n' -r ' '`.
```

## Line operations

| Command | Alias | Options | Effect |
|---|---|---|---|
| `sort` | `st` | `-r`/`--reverse`, `-n`/`--numeric-sort`, `-f`/`--ignore-case` | Locale-aware sort (`locale.strcoll`). As in GNU `sort -n`, `-n` compares each line's leading number, a line without one counts as 0, and ties compare the whole line |
| `dedupe` | | `-i`/`--ignore-case`, `--adjacent` | Drop duplicate lines anywhere, keep first occurrence and order; NFC-equivalent lines count as equal; `--adjacent` = GNU `uniq` (repeats next to each other only) |
| `reverse-lines` | `tac`, `rl` | | Reverse line order |
| `number-lines` | `nl` | `--starting-line-number N`, `-s`/`--number-separator STRING` | Prefix line numbers (default: from 1, TAB-separated). Long names as in GNU `nl`; unlike `nl`, blank lines are numbered and numbers are not padded |

## Separators & case

| Command | Alias | Example |
|---|---|---|
| `hyphen` | `hy` | `USER_ID` → `USER-ID` |
| `underscore` | `us` | `USER-ID` → `USER_ID` |
| `strip-commas` | `scm` | `1,234，567` → `1234567` (ASCII and full-width commas) |
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
| `unicode-escape` / `unicode-unescape` | `ue` / `uu` | `テスト` ↔ `テスト` |
| `html-escape` / `html-unescape` | `he` / `hu` | `<div>&` ↔ `&lt;div&gt;&amp;` |
| `fix-encoding` | `fe` | Repair mojibake by re-detecting the original encoding (`--threshold N`) |

An unescape or decode that fails (invalid input) exits 1 with an error; add `--fallback` to
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
| `json-format` | `jf` | `--indent N` (0-7 as in jq, default 2) | Pretty-print JSON |
| `json-compact` | `jc` | | JSON on one line (`jq -c`) |
| `markdown-table` | `mdt` | | TSV (Excel clipboard) or CSV → Markdown table; first row is the header |

## Text utilities

| Command | Alias | Options | Effect |
|---|---|---|---|
| `replace` | `rp` | `-e`/`--regexp PATTERN` (required, repeatable), `-r`/`--replace TEXT`, `-i`/`--ignore-case`, `-F`/`--fixed-strings` | Flags as in grep/ripgrep. Several `-e` replace any of them. The replacement uses Python/sed group references (`\1`, `\g<name>`), not ripgrep's `$1`; omitting `-r` deletes matches; `-F` makes patterns and replacement literal |
| `hash` | `hs` | `-a`/`--algorithm NAME` | Hex digest of the UTF-8 bytes as-is (default `sha256`). Flag as in GNU `cksum`, but `NAME` is a Python `hashlib` name (`sha256`, `sha3_256`, `md5`, …) |
| `count` | `wc` | | chars, non-space, words, lines, UTF-8 bytes (`non-space` suits Japanese manuscripts) |
| `slug` | `sl` | `--unicode` | `Hello, World! Café` → `hello-world-cafe`; `--unicode` keeps Japanese |
| `unix-to-date` | `ut` | `-u`/`--utc` | Unix time per line (s/ms auto-detected) → ISO 8601, local time by default |
| `date-to-unix` | | `--ms` | ISO 8601 per line → Unix seconds; no offset = local time |

```bash
echo "2026-07-17" | press replace -e '(\d+)-(\d+)-(\d+)' -r '\3/\2/\1'   # → 17/07/2026
printf "abc" | press hash -a md5             # → 900150983cd24fb0d6963f7d28e17f72
echo "1752710400" | press unix-to-date --utc # → 2025-07-17T00:00:00+00:00
```
