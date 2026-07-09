# Running press under endpoint security agents

Corporate PCs run monitoring agents — EDR (CrowdStrike Falcon, Microsoft
Defender for Endpoint, SentinelOne), endpoint DLP (Digital Guardian,
Forcepoint, Symantec DLP), and asset-management/activity-logging tools
(SKYSEA Client View, LanScope, AssetView). These agents intercept **process
launches, file opens, and clipboard operations** — exactly what a
clipboard-transformation CLI does — so press can feel noticeably slower on
some machines than others.

This page helps you identify which agent affects you and configure press to
minimize the impact.

## Step 1 — Find out what is running

```console
$ press daemon status --json
{
  ...
  "monitoring_agents": ["Digital Guardian", "Microsoft Defender AV"]
}
```

`monitoring_agents` lists well-known security agents detected on this
machine (best effort; requires the `daemon` extra). An empty list means
none of the known agents were found — not necessarily that none exist.

## Step 2 — Match your symptom

| Symptom | Likely cause | What helps |
|---|---|---|
| Every CLI call is slow | EDR/DLP scans each process launch + every file the interpreter opens | **Start the daemon** (below). Hotkeys skip process startup entirely, and the CLI automatically hands its work to the daemon too |
| `fix-encoding` is much slower than other commands | It imports `charset_normalizer` — 155 file opens versus 55 | Start the daemon; delegation makes every command cost the same |
| Only the *first* call is slow, later calls are fast | Antivirus on-access scan cache (normal) | Nothing needed; avoid `--onefile` builds, which re-extract and re-scan every run |
| Transforms themselves feel delayed | DLP evaluates every clipboard read/write | Ask IT whether press can be trusted; keep transforms via daemon (one process = one trust decision) |
| Hold/ClipboardGuard misbehaves, or security alerts appear | DLP also hooks paste keys and the clipboard — same hooks press uses | Set `intercept_paste_keys = false` (below); verify hold behavior on a monitored machine before relying on it |

## Step 3 — Recommended configuration

**Start the daemon — it speeds up the CLI too.** Monitoring agents charge a
toll per process launch and per file open; the daemon pays it once:

```console
$ press daemon start
```

Then use hotkeys (`Ctrl+Shift+0`, then a binding key) for transforms.

While the daemon runs, `press <command>` also gets faster automatically: the
CLI hands the text to the daemon over a local named pipe instead of importing
the transform module, which cuts the file opens a security agent has to
inspect. Nothing changes in what you type or what you get back, and if the
daemon is not running the CLI transforms the text itself exactly as before.

To turn delegation off (for troubleshooting), set `PRESS_NO_DAEMON=1`:

```console
$ $env:PRESS_NO_DAEMON = "1"     # PowerShell
$ press halfwidth                # always transforms in-process
```

**Under DLP (Digital Guardian, Forcepoint, …), disable the paste-key
hook.** DLP products intercept Ctrl+V at the same low level as press's
ClipboardGuard Layer 2; running both can conflict or trigger alerts.
Layer 1 (clipboard-monitor restore) still protects held text:

```toml
# %APPDATA%\press\config.toml
[hold]
intercept_paste_keys = false
```

**If your IT department allows exclusions**, the effective request is to
register the press executable (or `python.exe` running press) as a *trusted
application / process exclusion* in the endpoint agent — process-level
trust is the mechanism security vendors themselves recommend for tool
interoperability. press only reads/writes `%APPDATA%\press\`, a local
named pipe between its own processes, and the clipboard; it makes no
network connections. Every release publishes SHA-256 checksums
(`SHA256SUMS.txt`) so you can verify the artifact you were given. Code
signing via SignPath Foundation is set up but not yet active — see the
[code signing policy](../dev/code-signing.md).

**On Defender-only machines (developers):** placing your repositories and
virtual environments on a [Dev Drive](https://learn.microsoft.com/en-us/defender-endpoint/microsoft-defender-endpoint-antivirus-performance-mode)
switches Defender to asynchronous scanning for those volumes — safer than
folder exclusions and noticeably faster for interpreter startup.

## Why press is built this way

press keeps its CLI dependency-free and imports transform modules lazily —
each file open is one scan opportunity for a monitoring agent, so fewer
opens means less added latency. When a daemon is available the CLI skips
the transform import altogether, which caps every command at the same cost
(≈55 opens, measured on CPython 3.13) rather than paying for whatever that
command happens to import. Release builds use PyInstaller `--onedir`
specifically so antivirus scan caches stay valid between runs. A startup
performance test suite (`test/perf/`) guards these properties.
