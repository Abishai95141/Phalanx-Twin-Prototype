"""Step 1: rebuild a preview tail world, run it to the decision epoch, snapshot it, and check the
reproduction against the published v0.9 consumer tree (``data/v0.9/fleet``; never ``_restricted_labels``).

Usage: ./run.sh reproduce.py TJ107 [TJ108 TJ105 ...]
Writes ``video/data/forks/reproduction_<tail>.json`` (snapshots are not picklable, so each run rebuilds).
"""

from __future__ import annotations

import json
import sys
import time
from collections import Counter
from pathlib import Path

import pyarrow.compute as pc
import pyarrow.dataset as ds

from phx_forks import (
    PREVIEW_FLEET,
    TailWorld,
    bp,
    fmt_ist,
    iso_utc,
    ist_ns,
)

HERE = Path(__file__).resolve().parent
OUT = HERE.parents[1] / "data" / "forks"
T0 = ist_ns(2026, 6, 22, 8)  # decision epoch 2026-06-22 08:00 IST
T_CHECK = ist_ns(2026, 6, 22, 6)  # HYD-101 count check time
FORK_DAYS = 205  # scenario length: the 180-day preview + room for a 30-day horizon from day 168 (see README)
TOPICS = ("maint.records", "orders.commands", "orders.status", "events.bit_faults", "events.cautions")


def preview_rows(topic: str, tail: str, t_lt: int) -> list[dict]:
    p = PREVIEW_FLEET / topic
    if not p.exists():
        return []
    d = ds.dataset(p, format="parquet", partitioning=None)
    t = d.to_table()
    if topic == "orders.commands":
        t = t.filter(pc.field("target_tail_no") == tail)
    elif topic == "orders.status":  # no tail column: the orders of this tail's commands (ids may collide)
        cmd = ds.dataset(PREVIEW_FLEET / "orders.commands", format="parquet", partitioning=None).to_table()
        ids = sorted(set(cmd.filter(pc.field("target_tail_no") == tail).column("order_id").to_pylist()))
        t = t.filter(pc.is_in(pc.field("order_id"), value_set=__import__("pyarrow").array(ids, "string")))
    else:
        t = t.filter(pc.field("tail_no") == tail)
    ing = bp._contract().topics[topic].ingest_time
    return t.filter(pc.field(ing) < t_lt).to_pylist()


def canon(rows: list[dict]) -> Counter:
    out: Counter = Counter()
    for r in rows:
        out[repr(sorted((k, (v.hex() if isinstance(v, bytes) else v)) for k, v in r.items()))] += 1
    return out


def main(tails: list[str]) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for tail in tails:
        tw = TailWorld(tail, FORK_DAYS)
        s, info = tw.run_reference(T0)
        w = time.perf_counter()
        snap = tw.fs.snapshot(s)
        snap_s = time.perf_counter() - w
        doc: dict = {
            "tail": tail,
            "world": {
                "scenario": bp.FLEET_SCENARIO,
                "root_seed": hex(bp.FLEET_ROOT),
                "start": bp.FLEET_START.isoformat(),
                "fleet_days_built": FORK_DAYS,
                "m14_regime": bp.FLEET_REGIME,
                "policy": "scheduled/1.0.0",
                "dict_version": tw.builder.dict_version,
                "dict_hash": tw.builder.dict_hash,
                "contract_version": tw.contract.version,
                "contract_hash": tw.contract.hash,
            },
            "epoch": {"t_utc_ns": T0, "utc": iso_utc(T0), "ist": fmt_ist(T0), "t_kernel_ns": tw.kernel(T0)},
            "snapshot_id": snap.id,
            "wall_s_run_to_epoch": info["wall_s"],
            "wall_s_snapshot": round(snap_s, 3),
            "orders_submitted_before_epoch": info["orders_submitted_before_epoch"],
            "checks": {},
        }
        # --- exact reproduction: every consumer row ingested before the epoch, all columns ------------------
        for topic in TOPICS:
            mine = s.obs.as_of(T0 - 1, topic).to_pylist()
            mine = [r for r in mine if r.get("tail_no", tail) in (tail, None) or topic.startswith("orders.")]
            ref = preview_rows(topic, tail, T0)
            if topic == "maint.records":  # SHOP_FINDING rows have tail_no null in the preview (other worlds)
                mine = [r for r in mine if r["tail_no"] == tail]
            if topic == "orders.status":
                # order ids collide across the preview's per-tail worlds (TJ101/TJ102 share one), and
                # orders.status has no tail column: require every session row to be in the preview tree and
                # every preview record_id of this tail's orders to be in the session
                cm, cr = canon(mine), canon(ref)
                rid_m = {r["record_id"] for r in mine}
                rid_r = {r["record_id"] for r in ref}
                doc["checks"][f"{topic}_rows_before_epoch"] = {
                    "session": sum(cm.values()),
                    "preview_incl_colliding_worlds": sum(cr.values()),
                    "identical_all_columns": not (cm - cr) and rid_m == rid_r,
                    "only_in_session": sum((cm - cr).values()),
                    "note": "compared as session-rows subset of preview rows (order_id collisions)",
                }
                continue
            cm, cr = canon(mine), canon(ref)
            doc["checks"][f"{topic}_rows_before_epoch"] = {
                "session": sum(cm.values()),
                "preview": sum(cr.values()),
                "identical_all_columns": cm == cr,
                "only_in_session": sum((cm - cr).values()),
                "only_in_preview": sum((cr - cm).values()),
            }
        # --- the two named checks -------------------------------------------------------------------------
        bit = s.obs.as_of(T_CHECK, "events.bit_faults").to_pylist()
        hyd = [r for r in bit if r["tail_no"] == tail and r["event_code"] == "HYD-101"]
        prev_hyd = [
            r
            for r in preview_rows("events.bit_faults", tail, T_CHECK + 1)
            if r["event_code"] == "HYD-101"
        ]
        doc["checks"]["hyd101_bit_faults_ingested_by_2026-06-22_0600_IST"] = {
            "session": len(hyd),
            "preview": len(prev_hyd),
            "same_record_ids": sorted(r["record_id"].hex() for r in hyd)
            == sorted(r["record_id"].hex() for r in prev_hyd),
        }
        maint = s.obs.as_of(T0, "maint.records").to_pylist()
        av = sorted(
            (r for r in maint if r["record_type"] == "AVAILABILITY_STATE" and r["tail_no"] == tail),
            key=lambda r: (r["t_event"], r["record_version"]),
        )
        if av:
            cur = av[-1]["availability_state"]
            since = av[-1]["t_event"]
            doc["checks"]["availability_state_at_epoch"] = {"state": cur, "since_ist": fmt_ist(since)}
        (OUT / f"reproduction_{tail}.json").write_text(json.dumps(doc, indent=2) + "\n")
        print(json.dumps(doc, indent=2))


if __name__ == "__main__":
    main(sys.argv[1:] or ["TJ107"])
