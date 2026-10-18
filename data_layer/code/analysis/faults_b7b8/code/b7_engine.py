"""B7 engine signatures on the ground-run bench (PREREGISTRATION.md §3, B7-ENG-*-SIG, B7-ENG-C26, IRP diagnostic).

Per pair p (n = 5; identity B7ENG/E<p>/P<p>): one healthy run and seven faulty runs (F1-F7: M10 states set at
t = 0 through ``health.fault``), all on the same programme and identity (CRN). Steady value per hold = mean of
the recorded samples in the hold's last 7 s; the Muir cross-plots are inlet-corrected; the shift of a faulty
operating line is its mean relative distance from the healthy line interpolated at the faulty abscissae.

Usage: python -I b7_engine.py run OUT_DIR [--workers 2]   (resumable)
       python -I b7_engine.py analyse OUT_DIR
"""

from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ProcessPoolExecutor
from multiprocessing import get_context
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import bench as B  # noqa: E402

from phalanx.core.events import Event  # noqa: E402

T_REF, P_REF = 288.15, 101_325.0
HOLDS = ((12.0, 31.0), (27.0, 45.0), (42.0, 60.0), (57.0, 70.0), (72.0, 80.0), (87.0, 84.0), (102.0, 90.0))
HOLD_S, AVG_S = 15.0, 7.0
PROGRAMME = B.GroundRun(duration_s=117.0, pla=((0.0, 18.0), *HOLDS))
GOVERNED = 6  # the first six holds (PLA 31-84) are below IRP (87 deg)
N_PAIRS = 5
FAULTS: dict[str, tuple[tuple[str, float], ...]] = {
    "F1": (("eng:foul_fan", 0.02),),
    "F2": (("eng:foul_hpc", 0.02),),
    "F3": (("eng:ero_hpc", 0.05),),
    "F4": (("eng:ero_hpt", 0.026),),
    "F5": (("eng:ero_lpt", 0.008),),
    "F6": (("eng:abn_hpt", 0.03),),
    "F7": (("eng:extra_hpc_eta", -0.05),),
}
#: Muir Fig. 15 rows [TRANSFER: F404-400 CF-18], columns C1..C7: +1 up, -1 down, 0 no appreciable deviation
MUIR = {
    "fan": (-1, -1, -1, -1, -1, +1, +1),
    "hpc": (0, +1, -1, -1, -1, +1, +1),
    "hpt": (-1, -1, +1, +1, +1, +1, -1),
    "lpt": (0, +1, -1, 0, 0, +1, 0),
}
ROW_OF = {"F1": "fan", "F2": "hpc", "F3": "hpc", "F4": "hpt", "F5": "lpt", "F6": "hpt"}
MODE_OF = {
    "F1": "FM.ENG.FOULING",
    "F2": "FM.ENG.FOULING",
    "F3": "FM.ENG.EROSION",
    "F4": "FM.ENG.EROSION",
    "F5": "FM.ENG.EROSION",
    "F6": "FM.ENG.HPT_DETERIORATION",
    "F7": "FM.ENG.HPC_DAMAGE",
}
PLOTS = ("C1 W1c-N1c", "C2 N2c-N1c", "C3 Fgc-N2c", "C4 Wfmc-N2c", "C5 PS3/P1-N2c", "C6 T56c-P56/P1", "C7 N2c-P56/P1")
RECORDED = ("ENG.N1.V", "ENG.N2.V", "ENG.T1.V", "ENG.PS3.V", "ENG.WFM", "ENG.T5", "ENG.P5")


def _events(fault: str | None) -> list[Event]:
    if fault is None:
        return []
    return [
        Event(0, "health.fault", "health", {"state": s, "delta": float(v), "op": "set"}, source="b7")
        for s, v in FAULTS[fault]
    ]


def holds_of(r: B.BenchRun) -> dict[str, list[float]]:
    """Steady SI values per hold: recorded channels (eu_to_si) and truth instruments (eng.w2, eng.thrust,
    eng.a8, eng.t5, eng.n1) and the M08 active limiter (mode over the window)."""
    d = B._static()[0]
    out: dict[str, list[float]] = {}
    for c in RECORDED:
        v = np.asarray(d.eu_to_si(c, r.value[c]), np.float64)
        t = r.t_sample[c] * 1e-9
        out[c] = [float(v[(t >= t0 + HOLD_S - AVG_S) & (t < t0 + HOLD_S)].mean()) for t0, _ in HOLDS]
    tk = np.arange(r.n_steps) / 240.0
    for p in ("eng.w2", "eng.thrust", "eng.a8", "eng.t5", "eng.n1", "eng.n2", "eng.wf"):
        a = r.ports[p].reshape(r.n_steps, -1)[:, 0]
        out[p] = [float(a[(tk >= t0 + HOLD_S - AVG_S) & (tk < t0 + HOLD_S)].mean()) for t0, _ in HOLDS]
    lim = r.ports["fadec.active_limiter"].reshape(r.n_steps, -1)[:, 0]
    out["limiter"] = [
        float(np.bincount(lim[(tk >= t0 + HOLD_S - AVG_S) & (tk < t0 + HOLD_S)].astype(np.int64)).argmax())
        for t0, _ in HOLDS
    ]
    return out


def pair_job(job: tuple[int, bool]) -> dict:
    p, d3 = job
    ident = B.bench_identity("B7ENG", f"E{p}", f"P{p}")
    res = {"pair": p, "runs": {}}
    for fault in (None, *FAULTS):
        r = B.run_bench(PROGRAMME, ident, _events(fault), trim_at_start=d3)
        res["runs"]["H" if fault is None else fault] = holds_of(r)
    return res


def cross_plots(h: dict[str, list[float]]) -> dict[str, tuple[np.ndarray, np.ndarray]]:
    """The seven Muir cross-plots of one run's governed holds (x, y), inlet-corrected."""
    k = slice(0, GOVERNED)
    th = np.asarray(h["ENG.T1.V"][k]) / T_REF
    de = 1.0  # test-cell barometer = bench ambient (ISA sea level): P1 / P_REF
    n1c = np.asarray(h["ENG.N1.V"][k]) / np.sqrt(th)
    n2c = np.asarray(h["ENG.N2.V"][k]) / np.sqrt(th)
    w1c = np.asarray(h["eng.w2"][k]) * np.sqrt(th) / de
    fgc = np.asarray(h["eng.thrust"][k]) / de
    wfc = np.asarray(h["ENG.WFM"][k]) / (de * np.sqrt(th))
    ps3 = np.asarray(h["ENG.PS3.V"][k]) / (P_REF * de)
    t56 = np.asarray(h["ENG.T5"][k]) / th
    p56 = np.asarray(h["ENG.P5"][k]) / (P_REF * de)
    return {
        PLOTS[0]: (n1c, w1c),
        PLOTS[1]: (n1c, n2c),
        PLOTS[2]: (n2c, fgc),
        PLOTS[3]: (n2c, wfc),
        PLOTS[4]: (n2c, ps3),
        PLOTS[5]: (p56, t56),
        PLOTS[6]: (p56, n2c),
    }


def shift(healthy: tuple[np.ndarray, np.ndarray], faulty: tuple[np.ndarray, np.ndarray]) -> float:
    """Mean relative distance of the faulty points from the healthy line (nan if < 3 points in range)."""
    xh, yh = healthy
    o = np.argsort(xh)
    xh, yh = xh[o], yh[o]
    xf, yf = faulty
    inside = (xf >= xh[0]) & (xf <= xh[-1])
    if inside.sum() < 3:
        return float("nan")
    yi = np.interp(xf[inside], xh, yh)
    return float(np.mean((yf[inside] - yi) / yi))


def _ci(v: np.ndarray) -> tuple[float, float, float]:
    from scipy import stats

    v = v[np.isfinite(v)]
    if v.size < 2:
        return float("nan"), float("nan"), float("nan")
    m, s = float(v.mean()), float(v.std(ddof=1))
    h = float(stats.t.ppf(0.975, v.size - 1)) * s / np.sqrt(v.size)
    return m, m - h, m + h


def _suffix(d3: bool) -> str:
    """Result-file suffix: "_d3" for the DEVIATIONS D3 rerun (each run trimmed at its own initial inputs)."""
    return "_d3" if d3 else ""


def analyse(out: Path, d3: bool = False) -> dict:
    pairs = [json.loads(s) for s in (out / f"b7_engine_pairs{_suffix(d3)}.jsonl").read_text().splitlines()]
    pairs.sort(key=lambda d: d["pair"])
    table: dict = {"n_pairs": len(pairs), "faults": {}}
    for f in FAULTS:
        rows = {}
        for c, name in enumerate(PLOTS):
            v = np.array([shift(cross_plots(d["runs"]["H"])[name], cross_plots(d["runs"][f])[name]) for d in pairs])
            m, lo, hi = _ci(v)
            n_ok = int(np.isfinite(v).sum())
            # n = 5 pairs is pre-registered: a pair whose shift is not evaluable (fewer than 3 faulty points
            # inside the healthy range) makes the cell not evaluable; mean and CI over the evaluable pairs are
            # reported for information only
            cell = {"shifts": v.tolist(), "n_evaluable": n_ok, "mean": m, "ci95": [lo, hi]}
            if f in ROW_OF:
                exp = MUIR[ROW_OF[f]][c]
                cell["muir"] = exp
                if n_ok < len(pairs):
                    cell["verdict"] = f"FAIL (not evaluable: {n_ok}/{len(pairs)} pairs)"
                elif exp == 0:
                    cell["verdict"] = "PASS" if abs(m) < 0.01 else "FAIL"
                else:
                    ok = (lo > 0) if exp > 0 else (hi < 0)
                    cell["verdict"] = "PASS" if ok else "FAIL"
                cell["recorded"] = name not in (PLOTS[0], PLOTS[2])
            rows[name] = cell
        entry: dict = {"mode": MODE_OF[f], "states": FAULTS[f], "plots": rows}
        if f in ROW_OF:
            entry["row"] = ROW_OF[f]
            entry["verdict"] = "PASS" if all(r["verdict"] == "PASS" for r in rows.values()) else "FAIL"
            entry["verdict_recorded_only"] = (
                "PASS" if all(r["verdict"] == "PASS" for r in rows.values() if r["recorded"]) else "FAIL"
            )
        if f == "F7":
            c5, c4 = rows[PLOTS[4]]["mean"], rows[PLOTS[3]]["mean"]
            full = min(rows[PLOTS[4]]["n_evaluable"], rows[PLOTS[3]]["n_evaluable"]) == len(pairs)
            entry["c26"] = {
                "ps3_p1_shift": c5,
                "wfm_shift": c4,
                "fg_shift": rows[PLOTS[2]]["mean"],
                "band_ps3": [0.06, 0.10],
                "band_wfm": [0.06, 0.175],
                "verdict": "PASS" if (full and 0.06 <= c5 <= 0.10 and 0.06 <= c4 <= 0.175) else "FAIL",
            }
        # IRP diagnostic (hold 7, PLA 90): truth A8, N1, T5, thrust relative change; nozzle-loop state
        irp = {}
        for key in ("eng.a8", "eng.n1", "eng.t5", "eng.thrust", "eng.wf"):
            v = np.array([d["runs"][f][key][GOVERNED] / d["runs"]["H"][key][GOVERNED] - 1.0 for d in pairs])
            m, lo, hi = _ci(v)
            irp[key] = {"mean": m, "ci95": [lo, hi]}
        irp["healthy_limiter_codes"] = sorted({int(d["runs"]["H"]["limiter"][GOVERNED]) for d in pairs})
        entry["irp"] = irp
        table["faults"][f] = entry
    table["trim"] = "own initial inputs (DEVIATIONS D3)" if d3 else "pre-registered (healthy, no load)"
    (out / f"b7_engine{_suffix(d3)}.json").write_text(json.dumps(table, indent=1, sort_keys=True), encoding="utf-8")
    return table


def run(out: Path, workers: int, d3: bool = False) -> None:
    out.mkdir(parents=True, exist_ok=True)
    p = out / f"b7_engine_pairs{_suffix(d3)}.jsonl"
    done = {json.loads(s)["pair"] for s in p.read_text().splitlines()} if p.exists() else set()
    todo = [(k, d3) for k in range(N_PAIRS) if k not in done]
    with ProcessPoolExecutor(max_workers=workers, mp_context=get_context("spawn")) as ex:
        for res in ex.map(pair_job, todo):
            with open(p, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(res, sort_keys=True) + "\n")
            print(f"pair {res['pair']} done", flush=True)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=("run", "analyse"))
    ap.add_argument("out", type=Path)
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--d3", action="store_true", help="DEVIATIONS D3: trim each run at its own initial inputs")
    a = ap.parse_args(argv)
    if a.cmd == "run":
        run(a.out, a.workers, a.d3)
    else:
        t = analyse(a.out, a.d3)
        for f, e in t["faults"].items():
            print(f, e.get("row"), e.get("verdict"), e.get("verdict_recorded_only"), e.get("c26", {}).get("verdict", ""))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
