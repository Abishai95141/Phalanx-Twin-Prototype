"""Phase 0 go/no-go: build the 8 tail worlds to 2026-06-22 06:00 IST, publish the history, step one day
with the station routine only, publish the delta, and check it all against the published preview.

Usage: ./run.sh gonogo.py [run_dir]        (default: proto/runs/gonogo, wiped first)

Checks (all must pass):
1. History: every consumer row in our tree equals the preview's rows ingested by 22 Jun 06:00, all columns,
   for every topic (whole tree, all 8 worlds — ids collide across worlds in both, by design).
2. Delta: the rows published by the one-day step are exactly the preview's rows ingested in
   (22 Jun 06:00, 23 Jun 06:00] — with no orders of ours, the live world is the status quo.
3. Window: every row in a delta file has its ingest time inside the step's window.
4. Contract: every file carries the contract hash in its schema metadata.
5. Time: the one-day step for 8 tails takes ≤ 30 s.
Writes ``<run_dir>/gonogo_report.json``. Reads the preview's consumer tree only (never ``_restricted_labels``).
"""

from __future__ import annotations

import json
import shutil
import sys
import time
from collections import Counter
from pathlib import Path

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

import os

from datalayer import PREVIEW_FLEET as _PREVIEW_PARQUET, bp, fmt_ist, ist_ns
from world import Fleet

HERE = Path(__file__).resolve().parent
#: the reference tree: the published preview (Parquet), or its IPC copy where Parquet is unreliable (s390x)
PREVIEW_FLEET = Path(os.environ.get("PHX_PREVIEW_FLEET_IPC") or _PREVIEW_PARQUET)
T0 = ist_ns(2026, 6, 22, 6)  # first snapshot: 06:00 IST on the demo's first day
T1 = ist_ns(2026, 6, 23, 6)  # one day later
TOPICS = (
    "maint.records",
    "orders.commands",
    "orders.status",
    "events.bit_faults",
    "events.cautions",
    "usage.counters",
)
STEP_LIMIT_S = 30.0


def read_file(f: Path) -> pa.Table:
    if f.suffix == ".arrow":
        with pa.memory_map(str(f)) as src:
            return pa.ipc.open_file(src).read_all()
    return pq.ParquetFile(str(f)).read()


def part_files(root: Path) -> list[Path]:
    return sorted([*root.rglob("part-*.parquet"), *root.rglob("part-*.arrow")])


def file_schema(f: Path) -> pa.Schema:
    if f.suffix == ".arrow":
        with pa.memory_map(str(f)) as src:
            return pa.ipc.open_file(src).schema
    return pq.read_schema(f)


def rows(root: Path, topic: str, lo: int | None, hi: int) -> list[dict]:
    """Rows of ``topic`` under ``root`` (Parquet or Arrow IPC parts) with ingest time in (lo, hi]."""
    p = root / topic
    fs = part_files(p) if p.exists() else []
    if not fs:
        return []
    t = pa.concat_tables([read_file(f).replace_schema_metadata(None) for f in fs])
    ing = bp._contract().topics[topic].ingest_time
    t = t.filter(pc.less_equal(t.column(ing), pa.scalar(hi, pa.int64())))
    if lo is not None:
        t = t.filter(pc.greater(t.column(ing), pa.scalar(lo, pa.int64())))
    return t.to_pylist()


def canon(rs: list[dict]) -> Counter:
    def v(x):
        if isinstance(x, bytes):
            return x.hex()
        if isinstance(x, list):
            return tuple(v(y) for y in x)
        return x

    return Counter(repr(sorted((k, v(x)) for k, x in r.items())) for r in rs)


def compare(mine: list[dict], ref: list[dict]) -> dict:
    cm, cr = canon(mine), canon(ref)
    return {
        "ours": sum(cm.values()),
        "preview": sum(cr.values()),
        "identical_all_columns": cm == cr,
        "only_ours": sum((cm - cr).values()),
        "only_preview": sum((cr - cm).values()),
    }


def main(run_dir: Path) -> int:
    if run_dir.exists():
        shutil.rmtree(run_dir)
    run_dir.mkdir(parents=True)
    contract = bp._contract()
    report: dict = {
        "contract": {"version": contract.version, "hash": contract.hash},
        "t0": fmt_ist(T0),
        "t1": fmt_ist(T1),
        "checks": {},
    }

    w = time.perf_counter()
    fleet = Fleet(run_dir)
    report["build_worlds_s"] = fleet.build_s
    init = fleet.step(T0)
    report["init"] = {
        "wall_s": init["wall_s"],
        "per_tail_advance_s": {k: v["advance_s"] for k, v in init["tails"].items()},
        "routine_orders_before_t0": {k: tr.routine_orders for k, tr in fleet.tails.items()},
    }
    hist_root = run_dir / "fleet"
    ok = True
    hist = {topic: compare(rows(hist_root, topic, None, T0), rows(PREVIEW_FLEET, topic, None, T0)) for topic in TOPICS}
    report["checks"]["1_history_equals_preview"] = hist
    ok &= all(c["identical_all_columns"] for c in hist.values())

    step = fleet.step(T1)
    report["step"] = {
        "wall_s": step["wall_s"],
        "per_tail": {
            k: {"advance_s": v["advance_s"], "publish_s": v["publish_s"], "rows": v["rows"]}
            for k, v in step["tails"].items()
        },
    }
    delta = {topic: compare(rows(hist_root, topic, T0, T1), rows(PREVIEW_FLEET, topic, T0, T1)) for topic in TOPICS}
    report["checks"]["2_delta_equals_preview"] = delta
    ok &= all(c["identical_all_columns"] for c in delta.values())

    bad_window, n_rows = [], 0
    for tail_doc in step["tails"].values():
        for rel in tail_doc["files"]:
            topic = Path(rel).parts[1]
            t = read_file(run_dir / rel)
            ing = contract.topics[topic].ingest_time
            col = t.column(ing).to_pylist()
            n_rows += len(col)
            if any(not (T0 < x <= T1) for x in col):
                bad_window.append(rel)
    report["checks"]["3_delta_files_in_window"] = {
        "files": sum(len(v["files"]) for v in step["tails"].values()),
        "rows": n_rows,
        "files_outside_window": bad_window,
        "late_counter_rows": {k: v["rows"].get("late_counter_rows", 0) for k, v in step["tails"].items()},
    }
    ok &= not bad_window

    files = part_files(hist_root)
    wrong = [
        str(p.relative_to(run_dir))
        for p in files
        if (file_schema(p).metadata or {}).get(b"phalanx.contract_hash") != contract.hash.encode()
    ]
    report["checks"]["4_contract_hash_on_every_file"] = {"files": len(files), "wrong": wrong}
    ok &= not wrong

    report["checks"]["5_step_time"] = {"wall_s": step["wall_s"], "limit_s": STEP_LIMIT_S}
    ok &= step["wall_s"] <= STEP_LIMIT_S

    report["total_wall_s"] = round(time.perf_counter() - w, 1)
    report["verdict"] = "GO" if ok else "NO-GO"
    (run_dir / "gonogo_report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1]) if len(sys.argv) > 1 else HERE.parent / "runs" / "gonogo"))
