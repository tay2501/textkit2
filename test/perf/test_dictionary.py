"""Dictionary performance test at 50 k rows (ROADMAP v0.6.0 / SPEC §4.1).

TSV load plus lookup over a 50,000-row dictionary must complete in ≤ 100 ms.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

_MAX_LOAD_AND_LOOKUP_MS = 100.0  # ROADMAP v0.6.0 target
_ROWS = 50_000


def test_load_and_lookup_50k_rows(tmp_path: Path) -> None:
    from press.transforms.dictionary import dict_forward, load_tsv

    tsv = tmp_path / "big.tsv"
    tsv.write_text("".join(f"key{i}\tvalue{i}\n" for i in range(_ROWS)), encoding="utf-8")
    text = "\n".join(f"key{i * 7}" for i in range(1000))

    def _run() -> float:
        start = time.perf_counter()
        table = load_tsv(tsv)
        dict_forward(text, table=table)
        return (time.perf_counter() - start) * 1000

    _run()  # warmup (OS file cache, code paths)
    best_ms = min(_run() for _ in range(3))
    assert best_ms <= _MAX_LOAD_AND_LOOKUP_MS, (
        f"load+lookup took {best_ms:.1f} ms for {_ROWS} rows (target: {_MAX_LOAD_AND_LOOKUP_MS} ms)"
    )
