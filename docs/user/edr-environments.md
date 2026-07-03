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
| Every CLI call is slow | EDR/DLP scans each process launch + every file the interpreter opens | **Use the daemon** (below) — hotkeys skip process startup entirely |
| Only the *first* call is slow, later calls are fast | Antivirus on-access scan cache (normal) | Nothing needed; avoid `--onefile` builds, which re-extract and re-scan every run |
| Transforms themselves feel delayed | DLP evaluates every clipboard read/write | Ask IT whether press can be trusted; keep transforms via daemon (one process = one trust decision) |
| Hold/ClipboardGuard misbehaves, or security alerts appear | DLP also hooks paste keys and the clipboard — same hooks press uses | Set `intercept_paste_keys = false` (below); verify hold behavior on a monitored machine before relying on it |

## Step 3 — Recommended configuration

**Prefer the daemon over one-shot CLI calls.** Monitoring agents charge a
toll per process launch; the daemon pays it once:

```console
$ press daemon start
```

Then use hotkeys (`Ctrl+Shift+0`, then a binding key) for transforms.

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
interoperability. press only reads/writes `%APPDATA%\press\` and the
clipboard, and makes no network connections.

**On Defender-only machines (developers):** placing your repositories and
virtual environments on a [Dev Drive](https://learn.microsoft.com/en-us/defender-endpoint/microsoft-defender-endpoint-antivirus-performance-mode)
switches Defender to asynchronous scanning for those volumes — safer than
folder exclusions and noticeably faster for interpreter startup.

## Why press is built this way

press keeps its CLI dependency-free and imports transform modules lazily,
so a normal transform run opens ~40 files (measured on CPython 3.13) —
each file open is one scan opportunity for a monitoring agent, so fewer
opens means less added latency. Release builds use PyInstaller `--onedir`
specifically so antivirus scan caches stay valid between runs. A startup
performance test suite (`test/perf/`) guards these properties.
