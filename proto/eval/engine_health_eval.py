"""Planted-fault detection report for ``engines/engine_health.py`` on the generated engine trend (overlay v0.1).

For each run directory with an overlay (the live gonogo run and the training worlds), the model runs over every
engine's snapshots in takeoff order (causal: each step uses only snapshots ingested by then) and is compared with
the overlay's planted truth (``_restricted_labels/overlay`` — evaluation only):

- detection: first alert (CUSUM step or trend: days-to-limit p10 < 90 or margin < 10 °C) on the faulty engine at or
  after the fault's onset; delay after onset and lead time before the true margin reaches 0 °C (days and EFH);
- false alarms: alert episodes (rising edges) on healthy engines, or on a faulty engine before onset, per 100
  healthy flights;
- tracking: RMSE of the filtered margin against the true margin on healthy flights.

Writes proto/eval/<stem>.json and .md (default stem engine_health_eval).
Usage: <ground python> proto/eval/engine_health_eval.py [--out stem] [run_dir …]
       (default runs: runs/gonogo and runs/train/seed=*)
"""

from __future__ import annotations

import glob
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parent / "ground"), str(HERE.parent / "ground" / "engines")]

import engine_health as eh  # noqa: E402
from interfaces import DAY, NS, SOURCE_LABEL, Source  # noqa: E402
from store import Store  # noqa: E402

BIG = 2**62
TUNED_ON = "nothing: settings fixed by hand before evaluation (engine_health.py)"


def ist(t: int | None) -> str | None:
    import datetime as dt

    if t is None:
        return None
    return dt.datetime.fromtimestamp(t / NS, dt.timezone(dt.timedelta(hours=5, minutes=30))).strftime("%Y-%m-%d %H:%M")


def _read_truth(p: Path) -> pd.DataFrame:
    import pyarrow as pa

    if p.suffix == ".arrow":
        with pa.memory_map(str(p)) as src:
            return pa.ipc.open_file(src).read_all().to_pandas()
    return pd.read_parquet(p)


def evaluate(run: Path) -> dict:
    truth_dir = run / "_restricted_labels" / "overlay"
    tr = pd.concat([_read_truth(p) for p in sorted([*truth_dir.glob("truth-*.arrow"), *truth_dir.glob("truth-*.parquet")])],
                   ignore_index=True)
    tr = tr.drop_duplicates(["tail_no", "sortie_id"])
    planted = json.loads((truth_dir / "planted_faults.json").read_text())
    store = Store.for_run(run)
    steps = eh.run_tracks(store, BIG)
    st = pd.DataFrame([{k: getattr(s, k) for k in ("tail_no", "engine_serial", "sortie_id", "t_open", "t_ingest",
                                                  "efh", "level", "slope", "days_p10", "step_alert",
                                                  "trend_alert", "used", "note")} for s in steps])
    st["alert"] = st.step_alert | st.trend_alert
    st = st.merge(tr[["tail_no", "sortie_id", "true_margin_c", "faulty"]], on=["tail_no", "sortie_id"], how="left")
    faults = []
    faulty_eng = {}
    for f in planted["faults"]:
        if not f["engine"]:
            faults.append({**f, "detected": False, "reason": "fault never became active (no sortie after onset)"})
            continue
        tail, ser = f["engine"]
        faulty_eng[(tail, ser)] = f["onset_t"]
        e = st[(st.tail_no == tail) & (st.engine_serial == ser)].sort_values("t_open")
        et = tr[(tr.tail_no == tail) & (tr.engine_serial == ser)].sort_values("t_open")
        cross = et[et.true_margin_c <= 0]
        t_cross = int(cross.t_open.iloc[0]) if len(cross) else None
        efh_cross = float(cross.efh_before.iloc[0]) if len(cross) else None
        det = e[(e.t_open >= f["onset_t"]) & e.alert]
        d = {"fault_id": f["fault_id"], "mode": f["mode"], "tail_no": tail, "engine_serial": ser,
             "onset": ist(f["onset_t"]), "onset_efh": round(f["onset_efh"], 1),
             "true_limit_crossing": ist(t_cross), "true_limit_crossing_efh": None if efh_cross is None else round(efh_cross, 1),
             "data_until": ist(int(et.t_open.max())), "true_margin_at_end_c": round(float(et.true_margin_c.iloc[-1]), 1)}
        if len(det):
            r = det.iloc[0]
            d.update({
                "detected": True,
                "detected_at": ist(int(r.t_open)), "visible_at_ingest": ist(int(r.t_ingest)),
                "first_alert_kind": "step (CUSUM)" if r.step_alert else "trend (days to limit / margin)",
                "detection_delay_days": round((int(r.t_open) - f["onset_t"]) / DAY, 1),
                "detection_delay_efh": round(float(r.efh) - f["onset_efh"], 1),
                "true_margin_at_detection_c": round(float(r.true_margin_c), 1),
                "lead_time_days": None if t_cross is None else round((t_cross - int(r.t_ingest)) / DAY, 1),
                "lead_time_efh": None if efh_cross is None else round(efh_cross - float(r.efh), 1),
                "lead_time_note": None if t_cross is not None else
                f"true margin had not reached 0 °C by the end of the data ({d['true_margin_at_end_c']} °C left)",
            })
        else:
            d.update({"detected": False})
        faults.append(d)
    # false alarms: rising edges of the alert flag on healthy engine-flights
    healthy = []
    fa = 0
    for (tail, ser), e in st.sort_values("t_open").groupby(["tail_no", "engine_serial"]):
        onset = faulty_eng.get((tail, ser))
        h = e if onset is None else e[e.t_open < onset]
        healthy.append(h)
        a = h.alert.to_numpy()
        fa += int(a[0]) + int(np.sum(a[1:] & ~a[:-1])) if len(a) else 0
    hh = pd.concat(healthy) if healthy else st.iloc[:0]
    rmse = float(np.sqrt(np.mean((hh.level - hh.true_margin_c) ** 2))) if len(hh) else None
    return {
        "run": str(run),
        "world_seed": planted["world_seed"],
        "engines": int(st.groupby(["tail_no", "engine_serial"]).ngroups),
        "flights": int(len(st)),
        "healthy_flights": int(len(hh)),
        "snapshots_dropped": {k: int(st.note.str.contains(k).sum()) for k in ("frozen", "no valid", "outlier held")},
        "faults": faults,
        "false_alarm_episodes": fa,
        "false_alarms_per_100_flights": round(100 * fa / max(len(hh), 1), 3),
        "tracking_rmse_healthy_c": None if rmse is None else round(rmse, 2),
    }


def main(runs: list[Path], stem: str = "engine_health_eval") -> int:
    res = [evaluate(r) for r in runs]
    allf = [f for r in res for f in r["faults"]]
    det = [f for f in allf if f.get("detected")]
    leads = [f["lead_time_days"] for f in det if f.get("lead_time_days") is not None]
    fa = sum(r["false_alarm_episodes"] for r in res)
    hf = sum(r["healthy_flights"] for r in res)
    doc = {
        "source_label": SOURCE_LABEL[Source.OVERLAY],
        "model_id": eh.MODEL_ID,
        "model_version": eh.MODEL_VERSION,
        "note": "Pipeline proof on generated data: the model finds what was planted. Not validated physics, not "
                "real engine data.",
        "tuned_on": TUNED_ON,
        "summary": {
            "planted_faults": len(allf),
            "detected": len(det),
            "detected_before_true_limit": sum(1 for f in det if f.get("lead_time_days") is None or f["lead_time_days"] > 0),
            "lead_time_days_min_median_max": [min(leads), float(np.median(leads)), max(leads)] if leads else None,
            "detection_delay_days_median": float(np.median([f["detection_delay_days"] for f in det])) if det else None,
            "false_alarm_episodes": fa,
            "healthy_flights": hf,
            "false_alarms_per_100_flights": round(100 * fa / max(hf, 1), 3),
        },
        "runs": res,
    }
    (HERE / f"{stem}.json").write_text(json.dumps(doc, indent=1) + "\n")
    s = doc["summary"]
    lines = [
        "# Engine-health model: planted-fault detection",
        "",
        f"Source: **{doc['source_label']}** — generated data, not validated physics or real engine data. Model "
        f"`{eh.MODEL_ID}` {eh.MODEL_VERSION} (Kalman level + trend, CUSUM, washes as known change points); tuning: "
        f"{TUNED_ON}.",
        "",
        f"Planted faults: {s['planted_faults']}; detected {s['detected']}; detected before the true margin reached 0 °C: "
        f"{s['detected_before_true_limit']}. Lead time (days from the alert becoming visible to the true limit "
        f"crossing) min / median / max: {s['lead_time_days_min_median_max']}. Median delay after onset: "
        f"{s['detection_delay_days_median']} d. False alarms: {s['false_alarm_episodes']} episodes in "
        f"{s['healthy_flights']} healthy flights = **{s['false_alarms_per_100_flights']} per 100 flights**.",
        "",
        "| Run | Fault | Mode | Onset | Detected (kind) | Delay d / EFH | True margin at alert °C | True limit | Lead d / EFH |",
        "|---|---|---|---|---|---|---:|---|---|",
    ]
    for r in res:
        for f in r["faults"]:
            if f.get("detected"):
                lines.append(
                    f"| {Path(r['run']).name} | {f['fault_id']} ({f['engine_serial']}) | {f['mode']} | {f['onset']} | "
                    f"{f['detected_at']} ({f['first_alert_kind']}) | {f['detection_delay_days']} / {f['detection_delay_efh']} | "
                    f"{f['true_margin_at_detection_c']} | {f['true_limit_crossing'] or 'not reached (' + str(f['true_margin_at_end_c']) + ' °C left at ' + str(f['data_until']) + ')'} | "
                    f"{f['lead_time_days']} / {f['lead_time_efh']} |")
            else:
                lines.append(f"| {Path(r['run']).name} | {f['fault_id']} | {f['mode']} | {f.get('onset')} | not detected | | | | |")
    lines += ["", "| Run | Engines | Flights | Healthy flights | False-alarm episodes | per 100 flights | Tracking RMSE °C |",
              "|---|---:|---:|---:|---:|---:|---:|"]
    lines += [f"| {Path(r['run']).name} | {r['engines']} | {r['flights']} | {r['healthy_flights']} | "
              f"{r['false_alarm_episodes']} | {r['false_alarms_per_100_flights']} | {r['tracking_rmse_healthy_c']} |"
              for r in res]
    (HERE / f"{stem}.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    argv = sys.argv[1:]
    stem = "engine_health_eval"
    if "--out" in argv:
        i = argv.index("--out")
        stem = argv[i + 1]
        del argv[i : i + 2]
    args = [Path(a) for a in argv]
    if not args:
        root = HERE.parent / "runs"
        args = [root / "gonogo"] + [Path(p) for p in sorted(glob.glob(str(root / "train" / "seed=*")))]
    args = [a for a in args if (a / "_restricted_labels" / "overlay" / "planted_faults.json").exists()]
    sys.exit(main(args, stem))
