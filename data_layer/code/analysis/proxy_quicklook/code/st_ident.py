"""W2.4a-2 stage 1: steady identification of the proxy plant levels on 687-CAL (A-W2.4a-19, A-W2.4a-21).

The proxy M07 (`separate_fixed`) is put at each real quasi-steady operating point (``st_points.py``) - the
recorded flight condition (pressure altitude, Mach, TAT; static temperature at unit recovery, the U4
convention A-W2.4a-15), the recorded customer-bleed state and the recorded core speed (the steady solve frees
the fuel flow to hold N2) - and its steady fuel flow, fan speed and EGT-station temperature (T5, A-W2.4a-4)
are compared with the recorded FF, N1 and EGT. This compares the model's g (fuel vs core speed), h (fan vs
core speed) and EGT relations with CAL at the recorded conditions, regime by regime.

**Identified parameters** (bounded, physically meaningful; no per-point patch):

- off-design map modifiers of the fan and HPC (corrected flow and efficiency, ``1 + a (1 - Nc/Nc_des)^k``
  below design corrected speed; A-W2.4a-21);
- customer bleed from the recorded discretes by the proxy's own rule (``phalanx.proxy.bleed``: per-pack flow
  shared by the engines with an open bleed valve, wing+tail anti-ice flow shared likewise, engine anti-ice
  flow per engine); extracted at HPC exit (PROXY: the identified flows are HPC-exit-equivalent);
- a constant power off-take per engine (generator and hydraulic pumps), on top of the accessory load that
  scales with N2^2 (A-W2.4a-1).

**Residuals** per bin: ln(FF_model / FF_real) / 0.02, (N1_model - N1_real) / 1 %, (EGT_model - EGT_real) / 8
K, weighted by sqrt(min(n_points, 50)). Bins (the identification sample): points grouped by bleed state,
2,000-ft altitude, 0.04 Mach and 1 % corrected-core-speed cells; bin medians.

**Determinism:** every model evaluation starts each bin from a fixed start state (the bin's solution with the
neutral parameters, by N2 continuation from the design state) and, if Newton fails from there, follows a fixed
parameter homotopy; no state is carried between evaluations, so a fit is a pure function of the points and the
start values.

Usage::

    $PY -I analysis/proxy_quicklook/code/st_ident.py fit <points.json> <out.json> [workers] [param set]
    $PY -I analysis/proxy_quicklook/code/st_ident.py assess <points.json> <fit.json|none> <out.json> [workers]
"""

from __future__ import annotations

import json
import math
import os
import sys
import time
from multiprocessing import get_context

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # -I drops the script directory
import common  # noqa: F401  (puts src/ on the path, also in spawned workers)

LBH = 7936.641  # kg/s -> lb/h
FT = 0.3048
#: (name, kind, start, lo, hi). kind "p": kernel parameter (model.with_p); "bleed"/"pto": inputs
PARAMS = (
    ("fan_wc_mod_a", "p", 0.0, -0.6, 3.0),
    ("fan_wc_mod_k", "p", 1.5, 1.0, 4.0),
    ("fan_eff_mod_a", "p", 0.0, -0.6, 1.0),
    ("fan_eff_mod_k", "p", 1.5, 1.0, 4.0),
    ("hpc_wc_mod_a", "p", 0.0, -0.6, 3.0),
    ("hpc_wc_mod_k", "p", 1.5, 1.0, 4.0),
    ("hpc_eff_mod_a", "p", 0.0, -0.6, 1.0),
    ("hpc_eff_mod_k", "p", 1.5, 1.0, 4.0),
    ("rni_exp", "p", 0.0, 0.0, 0.5),  # Reynolds-number effect exponent (inlet RNI)
    ("fan_nc_mod_a", "p", 0.0, -0.3, 1.5),  # speed-line modifiers (map read at a modified speed)
    ("fan_nc_mod_k", "p", 1.5, 1.0, 4.0),
    ("hpc_nc_mod_a", "p", 0.0, -0.3, 1.5),
    ("hpc_nc_mod_k", "p", 1.5, 1.0, 4.0),
    ("w_pack", "bleed", 0.2, 0.0, 1.5),  # kg/s per running pack in flight (shared by the open valves)
    ("w_pack_gnd", "bleed", 0.2, 0.0, 1.5),  # kg/s per running pack on the ground (PH 2)
    ("w_eai", "bleed", 0.05, 0.0, 0.5),  # kg/s per engine with engine anti-ice on
    ("w_wai", "bleed", 0.3, 0.0, 2.0),  # kg/s wing + tail anti-ice (shared by the open bleed valves)
    ("pto_kw", "pto", 20.0, 0.0, 200.0),  # kW per engine, constant
)
NAMES = tuple(p[0] for p in PARAMS)
SCALES = {"FF": 0.02, "N1": 1.0, "EGT": 8.0}
#: model diagnostics kept per bin for the physical-sanity report (core/fan flows, T4, PS3, margins)
EXTRA = ("w2", "w25", "t41_ad", "ps3", "sm_fan", "sm_hpc", "pr_fan", "eta_fan", "eta_hpc", "wbleed")
CAP = 50


def isa_delta(alt_ft: float) -> float:
    h = float(alt_ft)
    return (1.0 - 6.87559e-6 * min(h, 36089.0)) ** 5.2559 * math.exp(-4.80634e-5 * max(h - 36089.0, 0.0))


def _popcount(v: int) -> int:
    return bin(int(v)).count("1")


def bleed_flow(b: dict, th: dict) -> float:
    """Customer bleed of engine 1 [kg/s] from the bin's recorded discretes, by the proxy's own rule
    (``phalanx.proxy.bleed.engine_bleed``; bins hold all-or-none BLV/EAI states, so engine 1 stands for
    all)."""
    from phalanx.proxy.bleed import BleedParams, engine_bleed

    p = BleedParams(th["w_pack"], th["w_eai"], th["w_wai"], th["pto_kw"] * 1e3, th["w_pack_gnd"])
    wai = 1 if (b["WAI_1"] or b["TAI"]) else 0
    disc = (np.array([b["BLV"]]), np.array([b["PACK"]]), np.array([b["EAI"]]), np.array([wai]))
    return float(engine_bleed(*disc, p, ground=np.array([bool(b["ground"])]))[0, 0])


def make_bins(points: list[dict]) -> list[dict]:
    """Bin medians of the quasi-steady points (all-or-none bleed and engine anti-ice states only)."""
    groups: dict[tuple, list[dict]] = {}
    for p in points:
        if p["BLV"] not in (0, 15) or p["EAI"] not in (0, 15) or p["WAI_2"] != 0:
            continue
        th = (p["TAT"] + 273.15) / 288.15
        n2c = p["N2"] / math.sqrt(th)
        key = (p["BLV"], _popcount(p["PACK"]), p["EAI"], int(bool(p["WAI_1"] or p["TAI"])), p["PH"] == 2,
               p["PH"] == 3,
               round(p["ALT"] / 2000.0), round(p["MACH"] / 0.04), round(n2c))  # fmt: skip
        groups.setdefault(key, []).append(p)
    out = []
    for key, ps in sorted(groups.items()):
        b = {k: float(np.median([q[k] for q in ps])) for k in ("ALT", "MACH", "TAT", "N1", "N2", "FF", "EGT")}
        b.update({"BLV": key[0], "PACK": ps[0]["PACK"], "EAI": key[2], "WAI_1": key[3], "TAI": 0, "ground":
        key[4],
                  "takeoff": key[5],
                  "n": len(ps), "PH": int(np.median([q["PH"] for q in ps])),
                  "flights": len({q["flight"] for q in ps})})  # fmt: skip
        out.append(b)
    return out


# ---------------------------------------------------------------- worker side
_W: dict = {}


def _init() -> None:
    from phalanx.engine.separate_design import build_separate_model

    m = build_separate_model()
    _W["m0"] = m
    _W["n1_100"] = float(m.params.value("n1_100pct"))
    _W["n2_100"] = float(m.params.value("n2_100pct"))


def _model(th: dict):
    return _W["m0"].with_p(**{k: th[k] for k, kind, *_ in PARAMS if kind == "p"})


def _inputs(m, b: dict, th: dict) -> np.ndarray:
    from phalanx.engine.layout import U_BLEED, U_NAMES
    from phalanx.engine.steady import ambient_inputs

    tatk = b["TAT"] + 273.15
    mach = b["MACH"]
    u = ambient_inputs(m, t_s=tatk / (1.0 + 0.2 * mach * mach), p_s=101325.0 * isa_delta(b["ALT"]), mach=mach)
    u[U_BLEED] = bleed_flow(b, th)
    u[U_NAMES.index("pto_power")] = th["pto_kw"] * 1e3
    return u


NEUTRAL = {
    n: (0.0 if kind != "p" or n.endswith("_a") or n == "rni_exp" else st) for n, kind, st, _lo, _hi in PARAMS
}


def _continuation(m, u, n2_target: float, x, steps: int):
    """Steady state at ``n2_target`` reached from state ``x`` in ``steps`` equal N2 steps (None on
    failure)."""
    from phalanx.engine.layout import X_N2
    from phalanx.engine.steady import steady_state

    n20 = float(x[X_N2])
    s = None
    for f in np.linspace(0.0, 1.0, steps + 1)[1:]:
        s = steady_state(m, u, x0=x, target=("n2", n20 + f * (n2_target - n20)))
        if not s.converged:
            return None
        x = s.x
    return s


def _neutral_start(b: dict):
    """The bin's steady state with the neutral parameters (unmodified maps, no bleed, no off-take), reached
    from the design state by N2 continuation (a deterministic function of the bin; None if it fails)."""
    from phalanx.engine.steady import design_state

    m = _model(NEUTRAL)
    u = _inputs(m, b, NEUTRAL)
    for steps in (12, 36):
        s = _continuation(m, u, b["N2"] / 100.0 * _W["n2_100"], design_state(m), steps)
        if s is not None:
            return s.x
    return None


def _start_chunk(items):
    out = []
    for i, b in items:
        x = _neutral_start(b)
        out.append((i, None if x is None else x.tolist()))
    return out


def _solve(b: dict, x0, th: dict):
    """Steady state of bin ``b`` at parameters ``th``: Newton from the neutral start; if that fails, a
    homotopy in the parameters from neutral (all parameters and bleed/off-take inputs moved together in 6,
    then 18 steps). Deterministic: the path depends only on the bin and ``th``."""
    from phalanx.engine.steady import steady_state

    if x0 is None:
        return None
    x0 = np.asarray(x0)
    target = ("n2", b["N2"] / 100.0 * _W["n2_100"])
    m = _model(th)
    s = steady_state(m, _inputs(m, b, th), x0=x0, target=target)
    if s.converged:
        return s
    for steps in (6, 18):
        x = x0
        s = None
        for lam in np.linspace(0.0, 1.0, steps + 1)[1:]:
            tl = {k: NEUTRAL[k] + lam * (th[k] - NEUTRAL[k]) for k in th}
            ml = _model(tl)
            s = steady_state(ml, _inputs(ml, b, tl), x0=x, target=target)
            if not s.converged:
                s = None
                break
            x = s.x
        if s is not None:
            return s
    return None


def _eval_chunk(args):
    """Model outputs at a chunk of bins for one parameter vector: (index, FF lb/h, N1 %, EGT degC, ok,
    aux)."""
    th, items = args
    from phalanx.engine.layout import U_WF, X_N1

    out = []
    for i, b, x0 in items:
        s = _solve(b, x0, th)
        if s is not None:
            a = s.aux_dict()
            ex = {k: a[k] for k in EXTRA}
            out.append((i, s.u[U_WF] * LBH, 100.0 * s.x[X_N1] / _W["n1_100"], a["t5"] - 273.15, True, ex))
        else:
            out.append((i, math.nan, math.nan, math.nan, False, None))
    return out


class Evaluator:
    """Model outputs at every bin for a parameter vector, on a process pool. The bins' neutral start states
    are computed once and sent with every task, so an evaluation does not depend on which worker runs which
    bin."""

    def __init__(self, bins: list[dict], workers: int):
        self.bins = bins
        self.pool = get_context("spawn").Pool(workers, initializer=_init)
        self.chunks = [list(range(j, len(bins), workers * 2)) for j in range(workers * 2)]
        x0: dict[int, list | None] = {}
        for part in self.pool.map(_start_chunk, [[(i, bins[i]) for i in ch] for ch in self.chunks]):
            x0.update(dict(part))
        self.x0 = [x0[i] for i in range(len(bins))]

    def __call__(self, th: dict):
        tasks = [(th, [(i, self.bins[i], self.x0[i]) for i in ch]) for ch in self.chunks]
        res: dict[int, tuple] = {}
        for part in self.pool.map(_eval_chunk, tasks):
            for r in part:
                res[r[0]] = r
        return [res[i] for i in range(len(self.bins))]

    def close(self):
        self.pool.close()
        self.pool.join()


#: stall-margin floors of the identified plant, (in flight, on the ground): penalty per 1 % of margin below
#: the floor. A steady point beyond the map stall line is not a valid operating point, and the replay needs
#: room for transients (the surge event model triggers at -1 %: a 0 % fan floor in flight gave 2-15 surges per
#: engine per CAL flight). In flight the fan keeps 5 % (about half of the generic plant's median 9 %). On the
#: ground the scaled low-PR map puts ground idle on its stall line (A-W2.4a-9; the generic plant has +0.5 %):
#: a 3 % ground floor was tried and cannot be met by the modifier family (cost unchanged, margins still 0), so
#: the ground floor is 0 and the replay trims at the highest lever (``proxy.system.trim_engine``).
SM_FLOOR = {"sm_fan": (0.05, 0.0), "sm_hpc": (0.05, 0.05)}
#: efficiency ceilings (a modified map must stay physical): penalty per 0.01 above the ceiling
ETA_CEIL = {"eta_fan": 0.93, "eta_hpc": 0.90}
N_RES = 3 + len(SM_FLOOR) + len(ETA_CEIL)


def residuals(rows, bins) -> np.ndarray:
    r = []
    for row, b in zip(rows, bins, strict=True):
        w = math.sqrt(min(b["n"], CAP))
        if not row[4]:
            r += [10.0 * w] * N_RES  # a failed solve is a large, finite penalty
            continue
        w_egt = (
            0.0 if b.get("takeoff") else w
        )  # the take-off roll EGT is not settled (st_points.takeoff_points)
        r += [w * math.log(max(row[1], 1.0) / b["FF"]) / SCALES["FF"], w * (row[2] - b["N1"]) / SCALES["N1"],
              w_egt * (row[3] - b["EGT"]) / SCALES["EGT"]]  # fmt: skip
        r += [w * max(0.0, fl[1 if b["ground"] else 0] - row[5][k]) / 0.01 for k, fl in SM_FLOOR.items()]
        r += [w * max(0.0, row[5][k] - cl) / 0.01 for k, cl in ETA_CEIL.items()]
    return np.asarray(r)


def theta_of(free: list[str], z: np.ndarray, fixed: dict) -> dict:
    th = {n: s for n, _k, s, _lo, _hi in PARAMS}
    th.update(fixed)
    th.update(dict(zip(free, (float(v) for v in z), strict=True)))
    return th


def summary(rows, bins) -> dict:
    """Median residuals per regime (the steady relations against CAL)."""
    reg: dict[str, list] = {}
    for row, b in zip(rows, bins, strict=True):
        if not row[4]:
            continue
        th2 = (b["TAT"] + 273.15) / 288.15
        n2c = b["N2"] / math.sqrt(th2)
        if b.get("takeoff"):
            name = "take-off (EGT not settled)"
        elif b["ground"]:
            name = "ground"
        elif n2c < 75:
            name = "flight idle"
        elif n2c < 90:
            name = "flight part power"
        elif b["ALT"] < 15000:
            name = "climb/cruise < 15 kft"
        else:
            name = "climb/cruise >= 15 kft"
        reg.setdefault(name, []).append((b["n"], row[1] / b["FF"] - 1.0, row[2] - b["N1"], row[3] - b["EGT"]))
    out = {}
    for k, v in reg.items():
        a = np.asarray(v)
        w = a[:, 0]
        out[k] = {"bins": len(v), "points": int(w.sum()),
                  "ff_rel_err_median": float(np.median(a[:, 1])), "n1_err_median": float(np.median(a[:, 2])),
                  "egt_err_median": float(np.median(a[:, 3])),
                  "ff_rel_err_wmean": float(np.average(a[:, 1], weights=w)),
                  "n1_err_wmean": float(np.average(a[:, 2], weights=w)),
                  "egt_err_wmean": float(np.average(a[:, 3], weights=w))}  # fmt: skip
    return out


def fit(
    points_json: str, out_json: str, workers: int = 10, free_spec: str = "all", start_json: str = ""
) -> None:
    """Fit the ``free`` parameters (comma list or "all"); the others, and the start values of the free ones,
    are the PARAMS start values or, with ``start_json``, that file's ``theta`` (clipped to the bounds)."""
    from scipy.optimize import least_squares

    pts = json.load(open(points_json))
    bins = make_bins(pts["points"])
    free = list(NAMES) if free_spec == "all" else free_spec.split(",")
    # a bleed parameter with no supporting bin is not identifiable: held at its start value
    if not any(b["ground"] and b["BLV"] for b in bins) and "w_pack_gnd" in free:
        free.remove("w_pack_gnd")
    if not any(b["EAI"] for b in bins) and "w_eai" in free:
        free.remove("w_eai")
    if not any(b["BLV"] and b["WAI_1"] for b in bins) and "w_wai" in free:
        free.remove("w_wai")
    spec = {p[0]: p for p in PARAMS}
    unknown = [n for n in free if n not in spec]
    if unknown:
        raise ValueError(f"unknown parameters {unknown}")
    lo = np.array([spec[n][3] for n in free])  # in the order of ``free`` (theta_of zips with it)
    hi = np.array([spec[n][4] for n in free])
    z0 = np.array([spec[n][2] for n in free])
    fixed: dict = {}
    if start_json:
        st = json.load(open(start_json))["theta"]
        fixed = {k: v for k, v in st.items() if k not in free}
        z0 = np.clip(np.array([st.get(n, spec[n][2]) for n in free], float), lo, hi)
    ev = Evaluator(bins, workers)
    t0 = time.time()
    rows0 = ev(theta_of(free, z0, fixed))
    r0 = residuals(rows0, bins)
    print(f"bins {len(bins)} points {sum(b['n'] for b in bins)} start cost {0.5 * float(r0 @ r0):.1f} "
          f"({time.time() - t0:.0f} s)", flush=True)  # fmt: skip
    hist = []

    def fun(z):
        rows = ev(theta_of(free, z, fixed))
        r = residuals(rows, bins)
        c = 0.5 * float(r @ r)
        hist.append(c)
        print(
            f"  cost {c:12.1f}  " + " ".join(f"{n}={v:.4g}" for n, v in zip(free, z, strict=True)), flush=True
        )
        return r

    sol = least_squares(fun, z0, bounds=(lo, hi), x_scale=np.maximum(hi - lo, 1e-3) / 4.0, diff_step=1e-3,
                        max_nfev=int(os.environ.get("ST_MAX_NFEV", "30")), method="trf")  # fmt: skip
    th = theta_of(free, sol.x, fixed)
    rows = ev(th)
    J = sol.jac
    try:
        cov = np.linalg.inv(J.T @ J) * (2.0 * sol.cost / max(1, J.shape[0] - J.shape[1]))
        se = np.sqrt(np.diag(cov)).tolist()
        cond = float(np.linalg.cond(J))
    except np.linalg.LinAlgError:
        se, cond = [math.nan] * len(free), math.inf
    ev.close()
    res = {"points": points_json, "n_bins": len(bins), "n_points": sum(b["n"] for b in bins), "free": free,
           "theta": th, "se_white": dict(zip(free, se, strict=True)), "jac_cond": cond,
           "cost_start": 0.5 * float(r0 @ r0), "cost": float(sol.cost), "nfev": int(sol.nfev),
           "status": int(sol.status), "message": sol.message, "summary_start": summary(rows0, bins),
           "summary": summary(rows, bins), "seconds": time.time() - t0,
           "bins": [{**b, "model_ff": r[1], "model_n1": r[2], "model_egt": r[3], "ok": r[4], "aux": r[5]}
                    for b, r in zip(bins, rows, strict=True)],
           "bins_start": [{"model_ff": r[1], "model_n1": r[2], "model_egt": r[3], "ok": r[4]}
                          for r in rows0]}  # fmt: skip
    with open(out_json, "w") as fh:
        json.dump(res, fh, indent=1)
    print(json.dumps({"theta": th, "cost": sol.cost, "summary": res["summary"]}, indent=1))


def evaluate(points_json: str, fit_json: str, out_json: str, workers: int = 10) -> None:
    pts = json.load(open(points_json))
    bins = make_bins(pts["points"])
    th = theta_of([], np.zeros(0), {})
    if fit_json != "none":
        th.update(json.load(open(fit_json))["theta"])
    ev = Evaluator(bins, workers)
    rows = ev(th)
    ev.close()
    r = residuals(rows, bins)
    res = {"points": points_json, "fit": fit_json, "theta": th, "n_bins": len(bins),
           "n_points": sum(b["n"] for b in bins), "cost": 0.5 * float(r @ r), "summary": summary(rows, bins),
           "failed": int(sum(not x[4] for x in rows)),
           "bins": [{**b, "model_ff": x[1], "model_n1": x[2], "model_egt": x[3], "ok": x[4], "aux": x[5]}
                    for b, x in zip(bins, rows, strict=True)]}  # fmt: skip
    with open(out_json, "w") as fh:
        json.dump(res, fh, indent=1)
    print(json.dumps({"cost": res["cost"], "failed": res["failed"], "summary": res["summary"]}, indent=1))


if __name__ == "__main__":
    if sys.argv[1] == "fit":
        fit(sys.argv[2], sys.argv[3], *(int(x) for x in sys.argv[4:5]), *sys.argv[5:7])
    else:
        evaluate(sys.argv[2], sys.argv[3], sys.argv[4], *(int(x) for x in sys.argv[5:6]))
