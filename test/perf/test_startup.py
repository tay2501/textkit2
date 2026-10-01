"""Startup performance regression tests (ROADMAP v0.6.0 / SPEC §4.1).

These guard the EDR-relevant startup metrics: endpoint security agents
(EDR/DLP/asset-management) intercept every process launch and file open,
so the number of modules imported and files opened at startup directly
scales the latency penalty on monitored machines.

Two guards:

1. Lazy-import contract — a plain transform run must not pull in
   ``argcomplete`` (only needed under the shell-completion hook) or
   ``importlib.metadata`` (only needed by ``--version``).
2. Budgets — wall-clock time for ``press --version`` (SPEC target: 2.0 s)
   and the file-open count of a transform run (measured ~40 on
   CPython 3.13/3.14 Linux; budget leaves headroom for platform variance).
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import time

import pytest

_MAX_VERSION_WALL_SECONDS = 2.0  # ROADMAP v0.6.0 / SPEC §4.1 target
_MAX_TRANSFORM_FILE_OPENS = 60  # Windows 2026-10: 32 on 3.13, 49 on 3.14 (argparse loads dataclasses); was 108 before lazy --version/argcomplete

_AUDIT_SNIPPET = """\
import sys

opens = 0

def _hook(event, args):
    global opens
    if event == "open":
        opens += 1

sys.addaudithook(_hook)
sys.argv = ["press", "snake"]
import runpy

try:
    runpy.run_module("press.__main__", run_name="__main__")
except SystemExit:
    pass
lazy_ok = "argcomplete" not in sys.modules and "importlib.metadata" not in sys.modules
print(f"RESULT opens={opens} lazy_ok={lazy_ok}", file=sys.stderr)
"""


def _run_audited_transform() -> tuple[int, bool]:
    """Run ``press snake`` in a subprocess and return (open_count, lazy_ok).

    The run is isolated from the developer's own press state: a leftover
    ``press.pid`` sends the CLI down the delegation path (ctypes, threading,
    json — ~14 extra opens) and a ``trace`` marker adds timing imports, so
    the count would depend on whether a daemon ever ran on this machine.
    """
    env = {**os.environ, "PRESS_NO_DAEMON": "1"}
    with tempfile.TemporaryDirectory() as appdata:
        env["APPDATA"] = appdata
        result = subprocess.run(
            [sys.executable, "-c", _AUDIT_SNIPPET],
            input="hello world",
            capture_output=True,
            text=True,
            check=True,
            env=env,
        )
    line = next(ln for ln in result.stderr.splitlines() if ln.startswith("RESULT "))
    fields = dict(part.split("=") for part in line.removeprefix("RESULT ").split())
    return int(fields["opens"]), fields["lazy_ok"] == "True"


class TestStartupWallTime:
    @pytest.mark.slow
    def test_version_completes_under_target(self) -> None:
        # Warmup absorbs one-time costs (pyc compilation, OS file cache, AV scan cache)
        subprocess.run(
            [sys.executable, "-m", "press", "--version"], capture_output=True, check=True
        )
        start = time.perf_counter()
        result = subprocess.run(
            [sys.executable, "-m", "press", "--version"], capture_output=True, check=True
        )
        elapsed = time.perf_counter() - start
        assert result.stdout.startswith(b"press ")
        assert elapsed <= _MAX_VERSION_WALL_SECONDS, f"startup took {elapsed:.2f}s"


class TestStartupFileIo:
    def test_transform_run_stays_lazy(self) -> None:
        """argcomplete and importlib.metadata must not load on a normal run."""
        _, lazy_ok = _run_audited_transform()
        assert lazy_ok, "argcomplete or importlib.metadata was imported on a plain transform run"

    def test_command_registry_avoids_dataclasses(self) -> None:
        """press.commands must not import dataclasses (inspect/ast/dis chain).

        On 3.13 that chain is 11 of ~43 file opens per transform run.  3.14's
        argparse pulls dataclasses in itself (via _colorize), so this checks
        the module in isolation rather than the whole run.
        """
        code = "import sys, press.commands; print('dataclasses' in sys.modules)"
        out = subprocess.run(
            [sys.executable, "-c", code], capture_output=True, text=True, check=True
        )
        assert out.stdout.strip() == "False"

    def test_transform_run_file_open_budget(self) -> None:
        """File opens per transform run stay within the EDR-relevant budget."""
        opens, _ = _run_audited_transform()
        assert opens <= _MAX_TRANSFORM_FILE_OPENS, (
            f"{opens} file opens at startup (budget: {_MAX_TRANSFORM_FILE_OPENS}) — "
            "did an import become eager? Each open is a scan opportunity for "
            "endpoint security agents."
        )
