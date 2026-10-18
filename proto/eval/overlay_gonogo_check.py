"""Check the engine overlay on the Phase 0 run (proto/runs/gonogo): history to 22 Jun 06:00 IST, then the one-day
delta to 23 Jun 06:00 — as the loop (S1) will call it after each ``Fleet.step``.

Checks: every overlay file carries contract 0.2.0's hash; delta rows are ingested inside the step window;
the run's ``fleet/`` tree is byte-for-byte unchanged; a second call writes nothing new (deterministic,
content-addressed). Report: proto/eval/overlay_gonogo_check.json.

Usage: proto/runner/run.sh proto/eval/overlay_gonogo_check.py [run_dir]
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "runner"))

from datalayer import bp, fmt_ist, ist_ns  # noqa: E402
from overlay import SOURCE_LABEL, overlay_step  # noqa: E402

T0, T1 = ist_ns(2026, 6, 22, 6), ist_ns(2026, 6, 23, 6)


def _table(p: Path) -> pa.Table:
    if p.suffix == ".arrow":
        with pa.memory_map(str(p)) as src:
            return pa.ipc.open_file(src).read_all()
    return pq.ParquetFile(p).read()


def tree_digest(root: Path) -> tuple[str, int]:
    h = hashlib.blake2b(digest_size=16)
    files = sorted(p for p in root.rglob("*") if p.is_file())
    for p in files:
        h.update(str(p.relative_to(root)).encode())
        h.update(hashlib.blake2b(p.read_bytes(), digest_size=16).digest())
    return h.hexdigest(), len(files)


def main(run: Path) -> int:
    c = bp._contract()
    before = tree_digest(run / "fleet")
    hist = overlay_step(run, None, T0)
    delta = overlay_step(run, T0, T1)
    again = overlay_step(run, T0, T1)
    after = tree_digest(run / "fleet")
    files = sorted([*(run / "overlay").rglob("part-*.parquet"), *(run / "overlay").rglob("part-*.arrow")])
    wrong_hash = [str(p) for p in files
                  if (_table(p).schema.metadata or {}).get(b"phalanx.contract_hash") != c.hash.encode()]
    out_of_window = []
    for rel in delta["files"]:
        col = _table(run / rel).column("t_ingest").to_pylist()
        if any(not (T0 < x <= T1) for x in col):
            out_of_window.append(rel)
    rep = {
        "source_label": SOURCE_LABEL,
        "run": str(run),
        "contract": {"version": c.version, "hash": c.hash},
        "history": {"to": fmt_ist(T0), "sorties": hist["sorties"], "rows": hist["rows"], "files": len(hist["files"])},
        "delta": {"window": [fmt_ist(T0), fmt_ist(T1)], "sorties": delta["sorties"], "rows": delta["rows"],
                  "files": len(delta["files"])},
        "checks": {
            "contract_hash_on_every_overlay_file": {"files": len(files), "wrong": wrong_hash},
            "delta_rows_in_window": {"files_outside_window": out_of_window},
            "fleet_tree_unchanged": {"before": before, "after": after, "ok": before == after},
            "repeat_call_identical": {"files": again["files"] == delta["files"], "rows": again["rows"]},
        },
    }
    ok = not wrong_hash and not out_of_window and before == after and again["files"] == delta["files"]
    rep["verdict"] = "PASS" if ok else "FAIL"
    (HERE / "overlay_gonogo_check.json").write_text(json.dumps(rep, indent=2) + "\n")
    print(json.dumps(rep, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1]) if len(sys.argv) > 1 else HERE.parent / "runs" / "gonogo"))
