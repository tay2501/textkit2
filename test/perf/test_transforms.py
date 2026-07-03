"""Per-transform throughput tests at 10 KB input (ROADMAP v0.6.0 / SPEC §4.1).

Every registered transform must process a 10 KB payload in ≤ 50 ms.
Commands are enumerated from the central registry, so newly added commands
are covered automatically. Inputs are valid per command (JSON commands get
JSON, base64-decode gets base64, fix-encoding gets real mojibake) — the
contract is throughput of the *success* path, not error handling.
"""

from __future__ import annotations

import base64
import importlib
import json
import time
from typing import Any

import pytest

from press.commands import PARAMETRIC_COMMANDS, SIMPLE_COMMANDS

_MAX_TRANSFORM_MS = 50.0  # ROADMAP v0.6.0 target at 10 KB
_TARGET_BYTES = 10 * 1024

_BASE_TEXT = ("Hello World foo_bar-baz  全角テストＡＢＣ１２３ line ここは日本語です\n" * 400)[
    :_TARGET_BYTES
]
_JSON_TEXT = json.dumps([{"key": i, "value": "x" * 20} for i in range(160)])  # ~10 KB
# UTF-8 bytes mis-decoded as latin-1 — classic mojibake fix_encoding must repair
_MOJIBAKE_TEXT = ("日本語のテキストです。" * 180).encode("utf-8").decode("latin-1")

_SPECIAL_INPUTS: dict[str, str] = {
    "json-format": _JSON_TEXT,
    "json-compress": _JSON_TEXT,
    "base64-decode": base64.b64encode(_BASE_TEXT.encode("utf-8")).decode("ascii"),
    "fix-encoding": _MOJIBAKE_TEXT,
}

# Kwargs needed for a deterministic success path
_SPECIAL_KWARGS: dict[str, dict[str, Any]] = {
    "fix-encoding": {"confidence_threshold": 0.0},
}

_ALL_COMMANDS = [(cmd.name, cmd.module, cmd.fn) for cmd in (*SIMPLE_COMMANDS, *PARAMETRIC_COMMANDS)]


@pytest.mark.parametrize(("name", "module", "fn_name"), _ALL_COMMANDS)
def test_transform_throughput_10kb(name: str, module: str, fn_name: str) -> None:
    fn = getattr(importlib.import_module(module), fn_name)
    text = _SPECIAL_INPUTS.get(name, _BASE_TEXT)
    kwargs = _SPECIAL_KWARGS.get(name, {})

    fn(text, **kwargs)  # warmup + validates the success path

    best_ms = float("inf")
    for _ in range(3):  # best-of-3 absorbs CI scheduler noise
        start = time.perf_counter()
        fn(text, **kwargs)
        best_ms = min(best_ms, (time.perf_counter() - start) * 1000)
    assert best_ms <= _MAX_TRANSFORM_MS, (
        f"{name}: {best_ms:.1f} ms for {len(text)} chars (target: {_MAX_TRANSFORM_MS} ms)"
    )
