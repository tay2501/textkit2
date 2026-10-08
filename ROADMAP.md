# press — Roadmap

**Current version:** 0.5.0 (unreleased; last tag v0.3.0) — updated 2026-10-09
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

## v0.5.0 — Config management CLI

Add the `press config` subcommand family.

- [x] `press config validate` — parse `config.toml` and report errors without starting the daemon
- [x] `press config reset [--key SECTION]` — overwrite with defaults (creates `.toml.bak` backup); `--key` limits to one section
- [x] `schema_version` field in `PressConfig` + forward-compatible detection (validate fails for unknown future versions)

---

## v0.6.0 — Performance benchmarks & CI enforcement

Implement the `test/perf/` suite from SPEC.md §4.1 so performance regressions are caught automatically.

- [x] `test/perf/test_startup.py` — wall-clock `press --version` (target ≤ 2.0 s), plus
      lazy-import contract and file-open budget (EDR-relevant; see docs/user/edr-environments.md)
- [x] `test/perf/test_transforms.py` — per-transform throughput at 10 KB input (target ≤ 50 ms),
      enumerated from the command registry so new commands are covered automatically
- [x] `test/perf/test_dictionary.py` — TSV load + lookup at 50 k rows (target ≤ 100 ms)
- [ ] `test/perf/test_daemon.py` (`@pytest.mark.windows_only`) — RSS ≤ 40 MB, CPU ≤ 0.1 %
      (deferred: needs a real tray/hotkey session; headless CI runners can't host it reliably)
- [x] CI enforcement: the suite lives under `testpaths`, so the normal `pytest` job runs it on
      every push for both OSes and both Python versions (no separate benchmark step needed)

---

## v1.0.0 — Distribution & public release

Freeze the CLI and config interfaces, publish to PyPI, and ship documentation.

- [ ] PyPI Trusted Publishing via `pypa/gh-action-pypi-publish` (no token required — SPEC.md §16.4)
- [ ] Sphinx documentation site published to GitHub Pages (`uv sync --group docs`)
- [ ] PowerShell tab completion via `Register-ArgumentCompleter` (README setup guide)
- [ ] Bump `Development Status` classifier to `5 - Production/Stable`
- [ ] Tag v1.0.0 and mark CLI + config schema as stable (no breaking changes without MAJOR bump)

---

## v1.x.0 — Future (unscheduled)

Items that require user feedback or external dependencies before committing.

- **Crash recovery / watchdog**: auto-restart daemon up to 5 times / 60 s with exponential backoff + jitter; `press daemon reset-failed` to clear terminal failed state (deferred from v0.4.0).
- **Non-blocking daemon logging**: `QueueHandler` + `QueueListener` for hotkey-callback-safe log writes (Python logging cookbook pattern; avoids blocking the pynput OS thread on disk I/O).
- **`argparse.deprecated=True`**: mark old aliases as deprecated when renaming commands (Python 3.13 feature).
- **macOS / Linux support** — `pynput` already supports both; main blocker is `pystray` on Linux (AppIndicator dependency). SPEC.md §13 defers this to after v1.0.0.
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
