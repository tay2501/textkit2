# press — Roadmap

**Current version:** 0.5.0 (unreleased; last tag v0.3.0) — updated 2026-11-06
**Status:** Beta (`Development Status :: 4 - Beta`)

---

## Completed

| Phase | Highlights | Release |
|---|---|---|
| Phase 1 | 20+ CLI transform commands (10 modules) | v0.1.0 |
| Phase 2 | TSV dictionary lookup, clipboard clear | v0.1.0 |
| Phase 3 | System-tray daemon, global hotkeys (leader-key pattern) | v0.2.0 |
| Phase 4 | Clipboard HOLD — dual-layer real-time protection | v0.2.0 |
| Phase 5 | Mojibake repair (`fix-encoding`), TOML config, lazy loading | v0.2.0 |
| Misc | Unicode normalization (NFC/NFD/NFKC/NFKD + `check-norm`), `enlarge-kana`, line ops | v0.3.0 |
| v0.4.0 | Daemon logs, JSON status, rotating log, nested subparsers, ClipboardGuard stub | v0.4.0 |

---

## v0.5.0 — Unreleased (all items done on `main`)

Full list in [CHANGELOG.md](CHANGELOG.md) under *Unreleased*.

- [x] `press config path` / `list` / `validate` / `reset [--section] [-y]`, `schema_version` with forward-compatible detection
- [x] Typed hotkey sequences (type the CLI name after `Ctrl+Alt+K`), default prefix `Ctrl+Alt+K`, ambiguity notifications
- [x] Real ClipboardGuard (`h`,`o` toggle, two layers, storm limit), CLI `press stash` (DPAPI), `press undo` + daemon `Shift+Z`
- [x] `press chain` and `[pipelines]`; daemon delegation over an owner-only named pipe
- [x] `type` hotkey (`SendInput`), `press notify off/on`, `press trace on/off`
- [x] New transforms: kana, hash, replace, count, slug, timestamps, markdown-table, number/reverse lines, strip-newlines, …; generators `genpass` / `uuid`
- [x] Flags and aliases renamed to the de facto tools' spelling (GNU coreutils, grep/ripgrep, jq)
- [x] Python 3.15 supported (CI lane, release `.exe`); `requires-python = ">=3.13,<3.16"`

---

## v0.6.0 — Performance benchmarks & CI enforcement

Implement the `test/perf/` suite so performance regressions are caught automatically.

- [x] `test/perf/test_startup.py` — wall-clock `press --version` (target ≤ 2.0 s), plus
      lazy-import contract and file-open budget (EDR-relevant; see docs/user/edr-environments.md)
- [x] `test/perf/test_transforms.py` — per-transform throughput at 10 KB input (target ≤ 50 ms),
      enumerated from the command registry so new commands are covered automatically
- [x] `test/perf/test_dictionary.py` — TSV load + lookup at 50 k rows (target ≤ 100 ms)
- [ ] `test/perf/test_daemon.py` (`@pytest.mark.windows_only`) — RSS ≤ 40 MB, CPU ≤ 0.1 %
      (deferred: needs a real tray/hotkey session; headless CI runners can't host it reliably)
- [x] CI enforcement: the suite lives under `testpaths`, so the normal `pytest` job runs it on
      every push for both OSes and all three Python versions (no separate benchmark step needed)

---

## v1.0.0 — Distribution & public release

Freeze the CLI and config interfaces, publish to PyPI, and ship documentation.

- [ ] PyPI Trusted Publishing via `pypa/gh-action-pypi-publish` (no token required) — blocked: the name `press` is taken on PyPI by an unrelated project, so a distribution name must be chosen first
- [ ] Activate SignPath code signing once the Foundation application is approved (`docs/dev/code-signing.md`)
- [ ] Sphinx documentation site published to GitHub Pages (`uv sync --group docs`)
- [ ] PowerShell tab completion via `Register-ArgumentCompleter` (README setup guide)
- [ ] Bump `Development Status` classifier to `5 - Production/Stable`
- [ ] Tag v1.0.0 and mark CLI + config schema as stable (no breaking changes without MAJOR bump)

---

## v1.x.0 — Future (unscheduled)

Items that require user feedback or external dependencies before committing.

- **Crash recovery / watchdog**: auto-restart daemon up to 5 times / 60 s with exponential backoff + jitter; `press daemon reset-failed` to clear terminal failed state (deferred from v0.4.0).
- **Non-blocking daemon logging**: `QueueHandler` + `QueueListener` for hotkey-callback-safe log writes (Python logging cookbook pattern; avoids blocking the pynput OS thread on disk I/O).
- **`argparse.deprecated=True`** after v1.0.0 only: until then renames delete the old spelling outright (no production users yet).
- **macOS / Linux support** — `pynput` already supports both; main blocker is `pystray` on Linux (AppIndicator dependency). Deferred to after v1.0.0.
- **Python 3.16** — admitted only after an allow-failure CI lane and a real-hardware daemon check prove pystray/pynput work.
- **PowerShell completion** — currently limited to bash/zsh/fish via `argcomplete`. Full PS7 support may require migrating to `typer` (pending startup-time measurement on HDD).
- **Additional transforms** — driven by real-world usage reports. Candidates: `rot13`, `wrap`.
- **Plugin / user-script support** — allow `~/.config/press/plugins/*.py` to register custom transform commands.

---

## Out of scope (permanent)

| Feature | Reason |
|---|---|
| Encryption / key management | Separate project (`coffer`) |
| Interactive REPL / TUI | Out of scope for a clipboard pipe tool |
| Cloud sync | Local-only by design |
| Non-Windows GUI | Daemon features are Win32-specific; CLI-only cross-platform use is already supported |
