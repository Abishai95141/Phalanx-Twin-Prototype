"""W2.4a-2 stage 6: quick look (A4, A5) - B1-B6 of the identified proxy on Tail 652 and 687-TEST.

Development only, no gate verdict. The proxy configuration is a ``runner`` spec (JSON: ``fadec``,
``engine``, ``bank``, ``sensor``), the one stages 4-5 identified on 687-CAL; nothing here is fitted.

Sets (the round-2 development lists, ``analysis/settling_experiment_round2/results/holdout_652_s20``, so the
bars and the round-2 S_R2b baseline are on the same flights):

- **652**: holdout = the 20 Tail-652 flights, partner (D_tail) = the 20 687-TEST flights, D_temp = the
  stored early/late halves of the 652 list; S_R2b = its stored ``battery.json`` D_sim (round 2, whole
  records);
- **687-TEST**: holdout = the 20 687-TEST flights, partner = the 20 Tail-652 flights, D_temp = the temporal
  halves of the TEST list (``samples.temporal_halves``); no stored S_R2b (round 2 did not run TEST as a
  holdout).

Each flight runs over its running window (``proxy.inputs.running_window``: engines running, from the levers
and PH only); the real record is sliced to the same samples, for the holdout, the partner and the halves, so
every comparison is window-for-window (round 2 used whole records: the bars are recomputed here and printed
next to round 2's, which measures the window effect on the bars).

Arms: the spec JSON is one ``runner`` spec (arm ``proxy``) or ``{"arms": {label: spec, ...}}``; every arm
runs every flight with the same identities (common random numbers), so arm contrasts attribute the tests to
the configuration difference (A4 per-test attribution).

Statistics: the M20 battery (``validation.battery``: ``flight_stats``, ``run_battery`` with the round-2
bootstrap ``SeedSequence(20261015)``, B1-B6 PASS / FAIL / INCONCLUSIVE against D_tail and D_temp) and, per
flight, the MF1 statistics (``mf1stats.record_stats``: B1 per phase class PH 4 / 5 / 6 / taxi, GOV classes,
B2 lags, spectral pair decomposition) for the A5 behaviours and the phase diagnostics; the B2 lags are also
split A/T engaged vs manual (FF->N2, the round-2 post hoc behaviour).

Sample: n = 20 flights per set (the round-2 development size; the bars, CIs and the S_R2b baseline exist at
this n). Data hygiene: 652 and 687-TEST are development / evaluation sets (never fitted); archive 2 is
refused by the path guard (``proxy.guard.check_path``); only files on the two lists are opened.

Usage::

    $PY -I analysis/proxy_quicklook/code/st6_quicklook.py <mat687> <mat652> <spec> <out> [workers] [limit]
"""

from __future__ import annotations

import json
import multiprocessing as mp
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # -I drops the script directory

import numpy as np
from common import REPO, ROOT
from mf1stats import record_stats

from phalanx.core.rng import KeyPath
from phalanx.fadec.codes import L_GOV_N2
from phalanx.proxy.guard import check_path
from phalanx.proxy.inputs import load_inputs, running_window
from phalanx.proxy.run import simulate_flight
from phalanx.validation.battery import BatteryConfig, Bootstrap, flight_stats, run_battery
from phalanx.validation.battery.stats import b2_stats
from phalanx.validation.dashlink import flight_date, load_record
from phalanx.validation.flightdata import FlightRecord
from phalanx.validation.samples import temporal_halves

R2 = REPO / "analysis" / "settling_experiment_round2" / "results" / "holdout_652_s20"
SPLITS = REPO / "analysis" / "settling_experiment" / "results" / "splits.csv"
SCENARIO = "w24a2-quicklook"


class QuickLookGuardError(PermissionError):
    """A file that is not on the quick-look lists."""


def lists() -> dict[str, list[str]]:
    keys = ("holdout", "partner", "early", "late")
    return {k: [x.strip() for x in open(R2 / f"list_{k}.txt") if x.strip()] for k in keys}


def _json(x):
    if isinstance(x, np.ndarray):
        return x.tolist()
    if isinstance(x, np.generic):
        return x.item()
    return str(x)


def allowed() -> dict[str, str]:
    """file -> set name, for the two quick-look lists only (652 holdout, 687-TEST partner)."""
    import csv

    sets = {r["file"]: r["set"] for r in csv.DictReader(open(SPLITS, newline=""))}
    L = lists()
    out = {}
    for f in L["holdout"]:
        if sets.get(f) != "652":
            raise QuickLookGuardError(f"{f} is not a Tail-652 flight")
        out[f] = "652"
    for f in L["partner"]:
        if sets.get(f) != "687-TEST":
            raise QuickLookGuardError(f"{f} is not a 687-TEST flight")
        out[f] = "687-TEST"
    return out


def path_of(fname: str, mat687: str, mat652: str) -> Path:
    s = allowed().get(fname)
    if s is None:
        raise QuickLookGuardError(f"{fname} is not on the quick-look lists")
    return check_path(Path(mat652 if s == "652" else mat687) / fname)


def _slice(rec: FlightRecord, a: int, n: int) -> FlightRecord:
    sl = slice(a, a + n)
    return FlightRecord(
        flight_id=rec.flight_id,
        rate_hz=rec.rate_hz,
        outputs={f: np.asarray(v)[:, sl] for f, v in rec.outputs.items()},
        pla=np.asarray(rec.pla)[:, sl],
        theta=np.asarray(rec.theta)[sl],
        delta=np.asarray(rec.delta)[sl],
        phase=np.asarray(rec.phase)[sl],
        units=rec.units,
        meta={**rec.meta, "window": f"{a}:{a + n}"},
    )


def b2_split(rec: FlightRecord, aten: np.ndarray) -> dict[str, float]:
    """B2 lead-lag (engine 1) on the A/T-engaged and on the manual airborne samples separately (each record
    restricted by zeroing nothing: the battery estimator on the masked sub-record)."""
    out = {}
    cfg = BatteryConfig()
    for lab, m in (("at", aten == 1), ("man", aten == 0)):
        if m.sum() < 400:
            continue
        Y = {f: np.asarray(rec.outputs[f])[:, m] for f in ("N1", "N2", "EGT", "FF")}
        b2 = b2_stats(Y, cfg)
        if b2 is not None:
            b2 = np.asarray(b2).reshape(4, -1)
            out[f"B2{lab}.FF>N2"] = float(b2[0, 0])
            out[f"B2{lab}.FF>N1"] = float(b2[0, 1])
    return out


def run_flight(args) -> dict:
    fname, k, mat687, mat652, arm, spec = args
    from runner import configure

    t0 = time.time()
    p = path_of(fname, mat687, mat652)
    inp = load_inputs(p)
    a, b = running_window(inp)
    cfg, fp = configure(spec)
    tail = "652" if allowed()[fname] == "652" else "687"
    sf = simulate_flight(
        cfg, inp, identity=KeyPath.of(scenario=SCENARIO, tail=f"T{tail}", sortie=k + 1), root=ROOT,
        window=(a, b), fadec_params=fp,
    )  # fmt: skip
    n = sf.record.n
    real = _slice(load_record(p), a, n)
    aten = inp.at_engage[a : a + n]
    gov = np.all(sf.regulator == L_GOV_N2, axis=0) if sf.regulator is not None else None
    return {
        "flight": fname,
        "arm": arm,
        "k": k,
        "window": [a, a + n],
        "fs_real": flight_stats(real),
        "fs_sim": flight_stats(sf.record),
        "mf1_real": record_stats(real, aten, gov),
        "mf1_sim": record_stats(sf.record, aten, gov),
        "b2split_real": b2_split(real, aten),
        "b2split_sim": b2_split(sf.record, aten),
        "n_surge": None if sf.n_surge is None else [int(x) for x in sf.n_surge],
        "seconds": round(time.time() - t0, 1),
    }


def main(mat687: str, mat652: str, spec_json: str, out_dir: str, workers: int = 4, limit: int = 0) -> None:
    """``limit`` > 0: smoke mode - the first ``limit`` flights of each list, per-flight statistics only."""
    with open(spec_json) as fh:
        spec = json.load(fh)
    arms = spec.get("arms") or {"proxy": spec}  # label -> runner spec; every arm runs every flight
    L = lists()
    os.makedirs(out_dir, exist_ok=True)
    flights = L["holdout"] + L["partner"]
    if limit > 0:
        flights = L["holdout"][:limit] + L["partner"][:limit]
    jobs = [(f, k, mat687, mat652, a, sp) for a, sp in arms.items() for k, f in enumerate(flights)]
    rows: dict[tuple[str, str], dict] = {}
    t0 = time.time()
    with mp.get_context("spawn").Pool(workers, maxtasksperchild=4) as pool:
        for i, r in enumerate(pool.imap_unordered(run_flight, jobs), 1):
            rows[(r["flight"], r["arm"])] = r
            tag = f"{r['arm']} {r['seconds']} s surge {r['n_surge']}"
            print(f"[{i}/{len(jobs)}] {r['flight']} {tag} ({time.time() - t0:.0f} s)", flush=True)
    res: dict = {"spec": spec, "n": {k: len(v) for k, v in L.items()}}
    keep = ("window", "mf1_sim", "b2split_sim", "n_surge", "seconds")
    first = next(iter(arms))
    res["per_flight"] = {
        f: {
            "window": rows[(f, first)]["window"],
            "mf1_real": rows[(f, first)]["mf1_real"],
            "b2split_real": rows[(f, first)]["b2split_real"],
            "arms": {a: {k: rows[(f, a)][k] for k in keep} for a in arms},
        }
        for f in flights
    }
    if limit > 0:
        res["smoke"] = {
            f"{f}|{a}": {"fs_real": r["fs_real"].__dict__, "fs_sim": r["fs_sim"].__dict__}
            for (f, a), r in rows.items()
        }
        with open(os.path.join(out_dir, "quicklook_smoke.json"), "w") as fh:
            json.dump(res, fh, indent=1, default=_json)
        print("wrote smoke", out_dir)
        return
    # 652 as holdout (round-2 lists), partner 687-TEST
    H = [rows[(f, first)]["fs_real"] for f in L["holdout"]]
    P = [rows[(f, first)]["fs_real"] for f in L["partner"]]
    idx = {f: i for i, f in enumerate(L["holdout"])}
    early = [idx[f] for f in L["early"]]
    late = [idx[f] for f in L["late"]]
    S = {a: [rows[(f, a)]["fs_sim"] for f in L["holdout"]] for a in arms}
    rep = run_battery(H, P, early, late, S, Bootstrap(np.random.SeedSequence(20261015)))
    res["652"] = rep.to_dict()
    # 687-TEST as holdout, partner 652, temporal halves of the TEST list
    dates = {f: flight_date(f) or "" for f in L["partner"]}
    e2, l2 = temporal_halves(L["partner"], dates)
    idx2 = {f: i for i, f in enumerate(L["partner"])}
    H2 = [rows[(f, first)]["fs_real"] for f in L["partner"]]
    S2 = {a: [rows[(f, a)]["fs_sim"] for f in L["partner"]] for a in arms}
    rep2 = run_battery(H2, H, [idx2[f] for f in e2], [idx2[f] for f in l2], S2,
                       Bootstrap(np.random.SeedSequence(20261015)))  # fmt: skip
    res["687-TEST"] = rep2.to_dict()
    res["round2_652_s20"] = json.load(open(R2 / "battery.json"))
    with open(os.path.join(out_dir, "quicklook.json"), "w") as fh:
        json.dump(res, fh, indent=1, default=_json)
    print("wrote", os.path.join(out_dir, "quicklook.json"))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], *(int(x) for x in sys.argv[5:7]))
