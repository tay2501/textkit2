# Code Style Guide

This document records the coding conventions for `press` and the rationale
behind each. All rules derive from **Effective Python** (Brett Slatkin, 3rd ed.)
and the project's own `CLAUDE.md`.

---

## Docstrings

**Rule: one short line maximum. Never add `Args:` / `Returns:` sections.**

Well-named identifiers already explain what a function does.
Sphinx-style parameter tables duplicate the type annotations and the caller's
mental model — they add maintenance burden without adding information.

```python
# Bad
def to_snake_case(text: str) -> str:
    """Convert each line to snake_case.

    Args:
        text: Input text; each line is converted independently.

    Returns:
        Text with each line converted to snake_case.
    """

# Good
def to_snake_case(text: str) -> str:
    """Convert each line to snake_case (handles camelCase, PascalCase, kebab-case)."""
```

Only add a docstring when the *why* or a non-obvious *constraint* is not
expressed by the identifier alone.

---

## Generator expressions over list accumulators

**Rule: pass generators directly to `join()` and similar consumers; avoid
intermediate lists built by `append` loops.**

```python
# Bad — builds a list only to discard it
result: list[str] = []
for i, word in enumerate(words):
    if i == 0:
        result.append(word.capitalize() if cap_first else word)
    else:
        result.append(word.capitalize() if cap_rest else word)
return joiner.join(result)

# Good — first/rest split + generator avoids enumerate bookkeeping
first = words[0].capitalize() if cap_first else words[0]
rest = (w.capitalize() if cap_rest else w for w in words[1:])
return joiner.join([first, *rest])
```

Exception: when the list is needed more than once, or when random access is
required, a list comprehension is correct.

---

## Nested functions without closure state belong at module level

**Rule: if a nested function does not read or assign any enclosing variable,
move it to module level.**

Benefits: independently testable, visible to type-checkers, no re-allocation on
every call.

```python
# Bad — _clean captures nothing from normalize_whitespace
def normalize_whitespace(text: str) -> str:
    def _clean(line: str) -> str:   # no closure variables
        line = line.replace("　", " ")
        ...

# Good — extracted to module level
def _clean_line(line: str) -> str:
    line = line.replace("　", " ")
    ...

def normalize_whitespace(text: str) -> str:
    ...
```

Contrast: `_key` inside `dedupe_lines` *does* close over `ignore_case` — it
stays nested by design.

---

## DRY via helper extraction (≥ 2 identical blocks)

**Rule: extract a private helper when the same `try/except` or multi-line
pattern appears in two or more sibling functions.**

```python
# Bad — identical try/except in json_format and json_compress
def json_format(text: str, *, indent: int = 2) -> str:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON: {exc}") from exc
    ...

# Good — single source of truth
def _load_json(text: str) -> Any:
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON: {exc}") from exc

def json_format(text: str, *, indent: int = 2) -> str:
    data = _load_json(text)
    ...
```

Do NOT extract for a single call site (YAGNI).

---

## Generator for repeated same-shape output lines

**Rule: when N lines share the same template, use a generator + `join` rather
than N separate variables.**

```python
# Bad — four bool variables + multi-part f-string
nfc = "yes" if n("NFC", text) else "no"
nfd = "yes" if n("NFD", text) else "no"
nfkc = "yes" if n("NFKC", text) else "no"
nfkd = "yes" if n("NFKD", text) else "no"
return f"NFC   {nfc}\nNFD   {nfd}\nNFKC  {nfkc}\nNFKD  {nfkd}\n"

# Good
return "".join(
    f"{form:<6}{'yes' if n(form, text) else 'no'}\n"
    for form in ("NFC", "NFD", "NFKC", "NFKD")
)
```

---

## EAFP over LBYL (project-wide)

Prefer `try/except` over `if x is not None` / `if key in dict`.

```python
# Bad (LBYL)
if key in d:
    return d[key]
return default

# Good (EAFP)
try:
    return d[key]
except KeyError:
    return default
```

Standard library functions like `dict.get()` are also fine — they are
idiomatic shorthand, not LBYL violations.

---

## Catch specific exceptions

Never `except Exception` unless the root cause is genuinely unknowable
(e.g. user-provided I/O in `_run_transform`). Always use the most specific
exception available.

```python
# Bad
try:
    return json.loads(text)
except Exception as exc:   # hides programming errors
    raise ValueError(...) from exc

# Good
try:
    return json.loads(text)
except json.JSONDecodeError as exc:
    raise ValueError(...) from exc
```

---

## No `for…else` / `while…else`

These constructs invert the usual meaning of `else` and confuse readers.
Use a flag variable or `break`/`return` pattern instead.
