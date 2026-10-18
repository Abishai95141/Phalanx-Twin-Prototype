"""Count confirmed shop findings in the training worlds BEFORE fitting anything (DEVELOPMENT.md Phase 1-C).

Reads the training worlds' consumer trees only, through the ground store (``Source.TRAIN``, one root per seed).
SHOP_FINDING rows have no tail: each is linked to its tail by job + serial + time (``hazard.link_findings``).
Keys are (world_seed, tail_no, record_id).

Writes proto/eval/train_counts.json and proto/eval/train_counts.md.
Usage: <ground python> proto/eval/train_counts.py [train_dir]   (default proto/runs/train)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parent / "ground"), str(HERE.parent / "ground" / "engines")]

import hazard as hz  # noqa: E402
from interfaces import SOURCE_LABEL, Source  # noqa: E402
from store import Root, Store  # noqa: E402

BIG = 2**62


def main(train: Path) -> int:
    man = json.loads((train / "train_manifest.json").read_text())
    seeds = sorted(d["world_seed"] for d in man["worlds"])
    seeds = sorted(set(seeds))
    horizon = man["horizon_days"]
    finds, spells = [], []
    for k in seeds:
        st = Store([Root(train / f"seed={k}" / "fleet", Source.TRAIN, world_seed=k)])
        finds.append(hz.count_findings(st, BIG, world_seed=k))
        spells.append(hz.build_spells(st, BIG, world_seed=k))
    f = pd.concat(finds, ignore_index=True)
    sp = pd.concat(spells, ignore_index=True)
    worlds = man["worlds_ok"]
    tail_years = worlds * horizon / 365.25
    f["hard_time"] = f.malfunction_code == hz.HARD_TIME
    linked = f.tail_no.notna()  # an unlinked finding has no job on a tail, so its hard-time status is unknown
    f["fault_confirmed"] = f.shop_finding.isin(hz.EVENT_FINDINGS) & ~f.hard_time & linked
    by_class = (
        f.groupby("klass")
        .agg(
            shop_findings=("rid", "size"),
            confirmed=("shop_finding", lambda s: int((s == "CONFIRMED").sum())),
            confirmed_hard_time=("hard_time", lambda s: int((s & (f.loc[s.index, "shop_finding"] == "CONFIRMED")).sum())),
            bcm=("shop_finding", lambda s: int((s == "BCM").sum())),
            rtok=("shop_finding", lambda s: int((s == "RTOK").sum())),
            unlinked=("tail_no", lambda s: int(s.isna().sum())),
        )
        .reset_index()
    )
    ev = sp.groupby("klass").agg(spells=("event", "size"), hazard_events=("event", "sum"),
                                 exposure_fh=("exposure_fh", "sum")).reset_index()
    by_class = ev.merge(by_class, on="klass", how="left").fillna(0)
    for c in by_class.columns:
        if c != "klass" and c != "exposure_fh":
            by_class[c] = by_class[c].astype(int)
    by_class["exposure_fh"] = by_class.exposure_fh.round(1)
    by_class["hazard_status"] = [
        "FIT" if n >= hz.MIN_EVENTS else "INSUFFICIENT_EVIDENCE" for n in by_class.hazard_events
    ]
    lk = f[f.tail_no.notna()]
    per_tail = (
        lk.groupby(["world_seed", "tail_no"])
        .agg(confirmed=("shop_finding", lambda s: int((s == "CONFIRMED").sum())),
             fault_confirmed=("fault_confirmed", "sum"))
        .reset_index()
    )
    per_tail["tail_years"] = round(horizon / 365.25, 3)
    per_tail["confirmed_per_tail_year"] = (per_tail.confirmed / per_tail.tail_years).round(3)
    per_tail["fault_confirmed_per_tail_year"] = (per_tail.fault_confirmed / per_tail.tail_years).round(3)
    events = sp[sp.event == 1]
    ev_keys = (
        f[f.fault_confirmed & f.tail_no.notna()][["world_seed", "tail_no", "rid", "klass", "shop_finding", "serial_no", "job_no"]]
        .rename(columns={"rid": "record_id"})
        .sort_values(["world_seed", "tail_no", "record_id"])
    )
    doc = {
        "source_label": SOURCE_LABEL[Source.TRAIN],
        "note": "Counted before any model was fitted. Synthetic simulator output, not validated, not real data.",
        "train_dir": str(train),
        "seeds": seeds,
        "worlds": worlds,
        "horizon_days": horizon,
        "tail_years": round(tail_years, 2),
        "definitions": {
            "confirmed": "SHOP_FINDING rows with shop_finding == CONFIRMED (as the brief asks)",
            "confirmed_hard_time": "of those, removals for hard-time expiry (job malfunction_code MAL-HT): not failures",
            "bcm": "SHOP_FINDING BCM: fault confirmed at depot (beyond base capability)",
            "hazard_events": "installation spells ending in a removal with a CONFIRMED or BCM finding, not hard-time",
            "linking": "SHOP_FINDING → tail by job + serial + time (latest REMOVE at or before the finding)",
            "keys": "(world_seed, tail_no, record_id)",
        },
        "totals": {
            "shop_findings": int(len(f)),
            "confirmed": int((f.shop_finding == "CONFIRMED").sum()),
            "confirmed_not_hard_time": int(((f.shop_finding == "CONFIRMED") & ~f.hard_time & linked).sum()),
            "confirmed_unlinked": int(((f.shop_finding == "CONFIRMED") & ~linked).sum()),
            "fault_confirmed_linked": int(f.fault_confirmed.sum()),
            "bcm": int((f.shop_finding == "BCM").sum()),
            "rtok": int((f.shop_finding == "RTOK").sum()),
            "unlinked": int(f.tail_no.isna().sum()),
            "hazard_events": int(events.event.sum()),
            "confirmed_per_tail_year": round(float((f.shop_finding == "CONFIRMED").sum()) / tail_years, 3),
            "fault_confirmed_per_tail_year": round(float(f.fault_confirmed.sum()) / tail_years, 3),
        },
        "by_class": by_class.to_dict(orient="records"),
        "per_tail_world": per_tail.to_dict(orient="records"),
        "fault_confirmed_keys": ev_keys.to_dict(orient="records"),
        "preview_reference": "preview v0.9: 0 CONFIRMED in about 3.7 tail-years (8 tails × 168 days)",
    }
    (HERE / "train_counts.json").write_text(json.dumps(doc, indent=1, default=int) + "\n")
    t = doc["totals"]
    lines = [
        "# Training-world event counts (before fitting)",
        "",
        f"Source: **{doc['source_label']}** — {worlds} tail-worlds ({len(seeds)} seeds × 8 tails) × {horizon} days = "
        f"{doc['tail_years']} tail-years, built with the live fleet's builder (`TailRunner`, new session roots). "
        "Synthetic and not validated.",
        "",
        f"Totals: {t['shop_findings']} shop findings; **{t['confirmed']} CONFIRMED** "
        f"({t['confirmed_not_hard_time']} linked and not hard-time, {t['confirmed_unlinked']} not linkable), {t['bcm']} BCM, {t['rtok']} RTOK, {t['unlinked']} not linkable "
        f"to a tail. Linked fault-confirmed findings: {t['fault_confirmed_linked']}. Fault-confirmed removals (CONFIRMED or BCM, not hard-time) used as hazard events: "
        f"**{t['hazard_events']}** ({t['fault_confirmed_per_tail_year']} per tail-year; CONFIRMED alone "
        f"{t['confirmed_per_tail_year']} per tail-year). Preview v0.9 for comparison: 0 CONFIRMED in about 3.7 tail-years.",
        "",
        "| Class | Spells | Hazard events | Exposure FH | CONFIRMED | of which hard-time | BCM | RTOK | Unlinked | Hazard |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for r in doc["by_class"]:
        lines.append(f"| {r['klass']} | {r['spells']} | {r['hazard_events']} | {r['exposure_fh']} | {r['confirmed']} | "
                     f"{r['confirmed_hard_time']} | {r['bcm']} | {r['rtok']} | {r['unlinked']} | {r['hazard_status']} |")
    lines += ["", f"Classes with fewer than {hz.MIN_EVENTS} hazard events return INSUFFICIENT_EVIDENCE.",
              "Per tail-world rates and the event keys are in `train_counts.json`."]
    (HERE / "train_counts.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1]) if len(sys.argv) > 1 else HERE.parent / "runs" / "train"))
