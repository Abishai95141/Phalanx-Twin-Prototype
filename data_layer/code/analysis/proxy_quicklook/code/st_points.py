"""W2.4a-2 stage 1: quasi-steady operating points of 687-CAL flights, per engine, for the steady
identification.

Data hygiene: CAL flights only (``common.guarded``: A3 guard, CAL membership, no Tail 652); MAT files parsed
by ``scipy.io.loadmat`` through the M20 adapter; paths are arguments. Real engine outputs are read here
because stage 1 **identifies** steady plant levels on 687-CAL (W2.4a-2 plan, item 1; fitting on CAL is
allowed).

A point is a 10-s block (40 samples at 4 Hz, non-overlapping, aligned to the record) in which one engine is
quasi-steady:

- running (N2 > 45 %), all four engines running;
- lever settled: PLA range <= 1.0 deg in the block and <= 2.0 deg over the 30 s before it (thermal settling of
  the EGT heat soak is not complete in 30 s; the slow part is reported, not filtered);
- outputs steady: N2 range <= 0.5 %, N1 range <= 1.0 %, FF range <= max(40 lb/h, 5 %), EGT range <= 10 degC;
- bleed/air-conditioning/anti-ice discretes (BLV, PACK, EAI, WAI_1, WAI_2, TAI) constant in the block.

Each point holds the block medians of the engine's N1, N2, EGT, FF and PLA and of ALT, MACH
(sentinel-cleaned), TAT and SAT, the altitude rate, the PH and ATEN codes and the discretes. The thresholds
are stated before any model comparison (they select steadiness, not agreement). Take-off roll points (PH 3)
use a 10-s lever settle and do not require a settled EGT (``takeoff_points``).

Usage::

    $PY -I analysis/proxy_quicklook/code/st_points.py <mat_dir> <first> <n_flights> <out.json> [n_anti_ice]

``first``/``n_flights`` select a slice of the MF1-D fixed order of the CAL flights; ``n_anti_ice`` adds the
first flights from position 40 of the order on whose wing/tail anti-ice is on in flight (selected on the
discretes only), so the anti-ice bleed is identifiable.
"""

from __future__ import annotations

import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # -I drops the script directory

from common import flight_order, guarded

from phalanx.validation.dashlink import _clean_mach, load_mat

RATE = 4.0
BLOCK = 40
SETTLE = 120
DISCRETES = ("BLV", "PACK", "EAI", "WAI_1", "WAI_2", "TAI")
CODES = ("PH", "ATEN")
LIMITS = {
    "pla_block": 1.0,
    "pla_settle": 2.0,
    "n2": 0.5,
    "n1": 1.0,
    "ff_abs": 40.0,
    "ff_rel": 0.05,
    "egt": 10.0,
}


def _held(p, n: int) -> np.ndarray:
    t4 = np.arange(n) / RATE
    return p.x[np.minimum((t4 * p.rate).astype(int), p.x.size - 1)]


def flight_arrays(mat_dir: str, fname: str) -> dict[str, np.ndarray]:
    """4-Hz arrays of one CAL flight (engine words (4, n); inputs and discretes (n,))."""
    F = load_mat(guarded(mat_dir, fname))
    n = min(F[f"N1_{k}"].x.size for k in (1, 2, 3, 4))
    n = min(n, F["PLA_1"].x.size, F["ALT"].x.size, F["MACH"].x.size)
    t4 = np.arange(n) / RATE
    a: dict[str, np.ndarray] = {}
    for f in ("N1", "N2", "EGT", "FF", "PLA"):
        a[f] = np.vstack([F[f"{f}_{k}"].x[:n].astype(float) for k in (1, 2, 3, 4)])
    a["ALT"] = F["ALT"].x[:n].astype(float)
    a["MACH"] = _clean_mach(F["MACH"].x[:n])
    for k in ("TAT", "SAT"):
        x = F[k].x.astype(float)
        a[k] = np.interp(t4, np.arange(x.size) / F[k].rate, x)
    for k in (*DISCRETES, *CODES):
        a[k] = _held(F[k], n).astype(np.int64)
    return a


def _rng(x: np.ndarray) -> float:
    return float(np.max(x) - np.min(x))


def steady_points(a: dict[str, np.ndarray], flight: str) -> list[dict]:
    n = a["ALT"].size
    out = []
    for s in range(SETTLE, n - BLOCK + 1, BLOCK):
        b = slice(s, s + BLOCK)
        if np.any(a["N2"][:, b] < 45.0):
            continue
        if any(_rng(a[k][b]) > 0 for k in DISCRETES):
            continue
        for e in range(4):
            pla = a["PLA"][e]
            if _rng(pla[b]) > LIMITS["pla_block"] or _rng(pla[s - SETTLE : s + BLOCK]) > LIMITS["pla_settle"]:
                continue
            ff = a["FF"][e, b]
            if (
                _rng(a["N2"][e, b]) > LIMITS["n2"]
                or _rng(a["N1"][e, b]) > LIMITS["n1"]
                or _rng(ff) > max(LIMITS["ff_abs"], LIMITS["ff_rel"] * float(np.median(ff)))
                or _rng(a["EGT"][e, b]) > LIMITS["egt"]
            ):
                continue
            pt = {"flight": flight, "engine": e + 1, "i0": s}
            for f in ("N1", "N2", "EGT", "FF", "PLA"):
                pt[f] = float(np.median(a[f][e, b]))
            for k in ("ALT", "MACH", "TAT", "SAT"):
                pt[k] = float(np.median(a[k][b]))
            pt["ALT_RATE_FPM"] = float((a["ALT"][s + BLOCK - 1] - a["ALT"][s]) / (BLOCK - 1) * RATE * 60.0)
            for k in (*DISCRETES, *CODES):
                pt[k] = int(np.median(a[k][b]))
            out.append(pt)
    return out + takeoff_points(a, flight)


def takeoff_points(a: dict[str, np.ndarray], flight: str) -> list[dict]:
    """Take-off roll points (PH 3): the lever is held for only 30-45 s, so the 30-s settling rule above never
    admits one. Here a 10-s block slides in 1-s steps through each take-off segment with a 10-s lever settle;
    N1, N2 and FF must be steady as above; the EGT is still rising (heat soak), so it is kept but marked
    ``egt_settled = False`` (the identification does not use it). The last admitted block per engine and
    segment is the point (the most settled one)."""
    out = []
    ph3 = np.flatnonzero(a["PH"] == 3)
    if ph3.size == 0:
        return out
    segs = np.split(ph3, np.flatnonzero(np.diff(ph3) > 1) + 1)
    for seg in segs:
        for e in range(4):
            best = None
            for s in range(max(int(seg[0]), BLOCK), int(seg[-1]) - BLOCK + 2, 4):
                b = slice(s, s + BLOCK)
                pla = a["PLA"][e]
                if np.any(a["N2"][:, b] < 45.0) or any(_rng(a[k][b]) > 0 for k in DISCRETES):
                    continue
                if (
                    _rng(pla[b]) > LIMITS["pla_block"]
                    or _rng(pla[s - BLOCK : s + BLOCK]) > LIMITS["pla_settle"]
                ):
                    continue
                ff = a["FF"][e, b]
                if (
                    _rng(a["N2"][e, b]) > LIMITS["n2"]
                    or _rng(a["N1"][e, b]) > LIMITS["n1"]
                    or _rng(ff) > max(LIMITS["ff_abs"], LIMITS["ff_rel"] * float(np.median(ff)))
                ):
                    continue
                best = s
            if best is None:
                continue
            b = slice(best, best + BLOCK)
            pt = {"flight": flight, "engine": e + 1, "i0": best, "egt_settled": False}
            for f in ("N1", "N2", "EGT", "FF", "PLA"):
                pt[f] = float(np.median(a[f][e, b]))
            for k in ("ALT", "MACH", "TAT", "SAT"):
                pt[k] = float(np.median(a[k][b]))
            pt["ALT_RATE_FPM"] = float(
                (a["ALT"][best + BLOCK - 1] - a["ALT"][best]) / (BLOCK - 1) * RATE * 60.0
            )
            for k in (*DISCRETES, *CODES):
                pt[k] = int(np.median(a[k][b]))
            out.append(pt)
    return out


def anti_ice_flights(mat_dir: str, k: int, start: int) -> list[str]:
    """The first ``k`` flights of the MF1-D order from position ``start`` on whose wing or tail anti-ice is on
    in flight (selection on the WAI_1/TAI/PH discretes only, never on engine outputs)."""
    out = []
    for fn in flight_order()[start:]:
        F = load_mat(guarded(mat_dir, fn))
        n = F["PH"].x.size
        ph = F["PH"].x.astype(int)
        on = np.zeros(n, bool)
        for key in ("WAI_1", "TAI"):
            x = F[key].x.astype(int)
            on |= (x[: min(n, x.size)] > 0) if x.size >= n else np.r_[x > 0, np.zeros(n - x.size, bool)]
        if np.any(on & (ph >= 4) & (ph <= 6)):
            out.append(fn)
            if len(out) == k:
                break
    return out


def main(mat_dir: str, first: int, n_flights: int, out_json: str, n_anti_ice: int = 0) -> None:
    flights = flight_order()[first : first + n_flights]
    if n_anti_ice:
        flights += anti_ice_flights(mat_dir, n_anti_ice, start=40)
    pts: list[dict] = []
    for fn in flights:
        p = steady_points(flight_arrays(mat_dir, fn), fn.replace(".mat", ""))
        pts += p
        print(fn, len(p), flush=True)
    meta = {"first": first, "n_flights": len(flights), "flights": flights, "limits": LIMITS, "block_s": BLOCK
    / RATE,
            "settle_s": SETTLE / RATE, "n_points": len(pts)}  # fmt: skip
    with open(out_json, "w") as fh:
        json.dump({"meta": meta, "points": pts}, fh)
    print("points", len(pts))


if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4], *(int(x) for x in sys.argv[5:6]))
