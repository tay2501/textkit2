# Installation

> **Applies to:** both.

## Requirements

- Windows 11 (Windows 10 may work but is not tested)
- Python 3.13 or 3.14 and [uv](https://docs.astral.sh/uv/) — or no Python with the release `.exe`

```{warning}
press is **not published on PyPI**. `pip install press` and `uv tool install press`
install an unrelated project that happens to share the name.
```

## Option A — release executable

Download `press-windows-x64.zip` from [GitHub Releases](https://github.com/tay2501/textkit2/releases),
verify it against `SHA256SUMS.txt`, unpack it, and add the `press` folder to `PATH`.
The executable includes the daemon.

## Option B — from source with uv

```bash
git clone https://github.com/tay2501/textkit2.git
cd textkit2
uv tool install .              # CLI only
uv tool install '.[daemon]'    # CLI + daemon (pystray, pynput)
```

`press` and `px` are then on `PATH` without activating a virtual environment.

## Verify

```bash
press --version
```

## Upgrade / uninstall

```bash
git pull && uv tool install --reinstall '.[daemon]'
uv tool uninstall press
```
