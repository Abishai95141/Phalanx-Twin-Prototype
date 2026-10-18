"""M8 (rough estimate, not over-built): usage-mode relevance of the backend choice, 30 tails x 2 years.

Usage mode (AD-10) evaluates sortie summaries with a surrogate, not the 240 Hz engine. Here a 1 Hz PWL-style
surrogate per sortie: PLA -> N2c demand (schedule) -> asymmetric first-order lag (tau 1.5 s up / 2.5 s down)
-> steady T5 from the T5 map at the steady fuel line -> lag (3 s) -> counters: time above 95 % N2c, a T5
exceedance-time integral (LUI-like), max T5, Type III-like cycles (idle <-> > 95 % N2c excursions).
Evaluated in NumPy vectorised across sorties (Python loop over 3,600 s), and in Numba (loop per sortie).

Fleet: 30 tails x 2 years x S sorties/tail/year, 1 h each. S = 200 [ASSUMPTION: per-aircraft hours are an
unavoidable assumption, architecture section 19; sweep 150-250]. Missions are generated once (feeding cost
reported separately). Measured on 1,000 sorties (3 reps) and extrapolated linearly.

Usage: python -I code/s09_m8_usage.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import rngblocks as R
import workload as W
from common import RESULTS, machine_info, now, save_json, stats

NS = 1000
REPS = 3
TAILS, YEARS = 30, 2
SORTIES_PER_YEAR = {"low": 150, "mid": 200, "high": 250}


def make_inputs(n):
    pla = np.empty((n, 3600))
    t2 = np.empty((n, 3600))
    t0 = now()
    for i in range(n):
        m = W.make_mission(R.generator(("bench", "M8", f"sortie{i:06d}", "M02.mission")), "sortie", 3600.0)
        tk = np.arange(3600.0)
        pla[i] = np.interp(tk, m.t, m.pla)
        alt, mach = np.interp(tk, m.t, m.alt), np.interp(tk, m.t, m.mach)
        t2[i] = W.inlet(alt, mach, m.dT_isa)[0]
    return pla, t2, now() - t0


def surrogate_numpy(pla, t2, T: W.Tables):
    n = pla.shape[0]
    th = t2 / W.T0
    dem = np.interp(pla, T.pla_x, T.pla_y)
    n2 = dem[:, 0].copy()
    t5 = np.zeros(n)
    au, ad, at = 1 - np.exp(-1 / 1.5), 1 - np.exp(-1 / 2.5), 1 - np.exp(-1 / 3.0)
    above = np.zeros(n)
    lui = np.zeros(n)
    t5max = np.zeros(n)
    cycles = np.zeros(n)
    hi = np.zeros(n, bool)
    for s in range(pla.shape[1]):
        d = dem[:, s]
        n2 = n2 + np.where(d > n2, au, ad) * (d - n2)
        t5ss = th[:, s] ** 0.73 * W.t5c_fn(n2, W.wf_ss(n2))
        t5 = np.where(s == 0, t5ss, t5 + at * (t5ss - t5))
        above += n2 > 0.95
        lui += np.maximum(t5 - 1050.0, 0.0)
        t5max = np.maximum(t5max, t5)
        up = (~hi) & (n2 > 0.95)
        down = hi & (n2 < 0.75)
        cycles += up
        hi = np.where(up, True, np.where(down, False, hi))
    return np.stack([above, lui, t5max, cycles], 1)


def surrogate_numba_factory():
    from numba import njit, prange

    @njit(parallel=True, cache=True)
    def run(pla, t2, plx, ply):
        n, L = pla.shape
        out = np.empty((n, 4))
        au, ad, at = 1 - np.exp(-1 / 1.5), 1 - np.exp(-1 / 2.5), 1 - np.exp(-1 / 3.0)
        for i in prange(n):
            n2 = np.interp(pla[i, 0], plx, ply)
            t5 = 0.0
            above = lui = t5max = cycles = 0.0
            hi = False
            for s in range(L):
                d = np.interp(pla[i, s], plx, ply)
                n2 = n2 + (au if d > n2 else ad) * (d - n2)
                x = max(n2 - 0.6, 0.0)
                t5c = max(680.0 + 410.0 * (x / 0.4) ** 1.3, 350.0)  # T5 map on the steady fuel line
                t5ss = (t2[i, s] / 288.15) ** 0.73 * t5c
                t5 = t5ss if s == 0 else t5 + at * (t5ss - t5)
                above += n2 > 0.95
                lui += max(t5 - 1050.0, 0.0)
                t5max = max(t5max, t5)
                if (not hi) and n2 > 0.95:
                    cycles += 1.0
                    hi = True
                elif hi and n2 < 0.75:
                    hi = False
            out[i, 0], out[i, 1], out[i, 2], out[i, 3] = above, lui, t5max, cycles
        return out

    return run


def main():
    T = W.make_tables()
    pla, t2, t_gen = make_inputs(NS)
    res = {"machine": machine_info(), "sorties_measured": NS, "reps": REPS, "mission_generation_s": t_gen}
    ts = []
    for _ in range(REPS):
        t0 = now()
        a = surrogate_numpy(pla, t2, T)
        ts.append(now() - t0)
    res["surrogate_numpy_s"] = stats(ts)
    run = surrogate_numba_factory()
    t0 = now()
    b = run(pla, t2, T.pla_x, T.pla_y)
    res["surrogate_numba_first_call_s"] = now() - t0
    ts = []
    for _ in range(REPS):
        t0 = now()
        b = run(pla, t2, T.pla_x, T.pla_y)
        ts.append(now() - t0)
    res["surrogate_numba_s"] = stats(ts)
    res["numpy_vs_numba_max_rel_diff"] = float(np.max(np.abs(a - b) / np.maximum(np.abs(a), 1e-12)))
    # extrapolate per scenario; telemetry-mode comparison from M1 (single core, engine loop only)
    m1 = RESULTS / "m1_sortie_hour.json"
    import json

    m1r = json.load(open(m1))["rows"] if m1.exists() else {}
    per = {k: res[k]["median"] / NS for k in ("surrogate_numpy_s", "surrogate_numba_s")}
    per["mission_generation_s"] = t_gen / NS
    res["fleet"] = {}
    for lvl, spy in SORTIES_PER_YEAR.items():
        n = TAILS * YEARS * spy
        row = {"sorties": n, **{f"{k}_total": v * n for k, v in per.items()}}
        for name in ("numba_single", "jax_single_unroll4"):
            if name in m1r:
                row[f"telemetry_all_sorties_{name}_core_h"] = m1r[name]["kernel_s"]["median"] * n / 3600.0
        res["fleet"][lvl] = row
    print(res["fleet"], file=sys.stderr)
    save_json("m8_usage.json", res)


if __name__ == "__main__":
    main()
