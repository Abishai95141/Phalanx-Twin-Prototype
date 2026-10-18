"""W2.4a-2 stage 5: identification windows on 687-CAL, from the inputs only (no engine word is read).

The staged indirect identification (AD-52 item 5; W2.4a-1 A2 split) needs two kinds of excitation:

- **A/T windows** (plant inertias and word lags, the governor held): airborne (PH 4-6), A/T engaged
  throughout, every lever above cutoff, N1 command >= ``N1C_MIN`` % (the A/T floor at the idle-stop demand
  does not bind); the ``AT_S`` window inside each such stretch with the largest total |dN1C| that holds both
  command increases and decreases (>= ``AT_MIN_DIR`` % each: accel and decel, AD-34);
- **manual windows** (governor gains, the plant held): the airborne approach with the A/T off (PH 6-7, WOW =
  1: airborne in the DASHlink polarity); the ``MAN_S`` window with the largest total |dPLA| of engine 1 (>=
  ``MAN_MIN_SCORE`` deg). Taxi lever bursts are left out (ground idle sits on the scaled fan map's stall
  line, A-W2.4a-9/-21; the surge PROXY would enter the window).

One window per kind and flight (the best), flights in the MF1-D order, until ``N_AT`` / ``N_MAN``. Each
window is screened by ``st5_ident.py`` for the governed regime before fitting.

Sample (stated before running): n_at = 4 A/T windows of 120 s and n_man = 3 manual windows of <= 160 s, one
per flight: the A2 split recovered the plant within 5 % from one 120 s A/T window and the gains from one
manual flight at texture only; real data carry the disturbances, hence several windows. The size is also
bounded by the local compute rule (a stage above ~1 CPU-hour goes to Kaggle): about 20 s of identification-
model time per residual evaluation.

Usage::

    $PY -I analysis/proxy_quicklook/code/st5_segments.py <mat_dir> <out.json> [n_scan]
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # -I drops the script directory

import numpy as np
from common import flight_order, guarded
from spectral import runs

from phalanx.proxy.inputs import load_inputs

RATE = 4.0
AT_S = 120.0
MAN_S = 160.0
N_AT, N_MAN = 4, 3
N1C_MIN = 60.0
AT_MIN_DIR = 0.5
MAN_MIN_S = 60.0
MAN_MIN_SCORE = 5.0


def _best_window(a: int, b: int, act: np.ndarray, L: int) -> tuple[int, int, float]:
    """The L-sample window inside [a, b) with the largest activity sum (the whole stretch if shorter)."""
    if b - a <= L:
        return a, b, float(act[a:b].sum())
    c = np.r_[0.0, np.cumsum(act[a:b])]
    sums = c[L:] - c[:-L]
    i = int(np.argmax(sums))
    return a + i, a + i + L, float(sums[i])


def scan(mat_dir: str, fname: str) -> dict[str, tuple[int, int, float] | None]:
    inp = load_inputs(guarded(mat_dir, fname))
    ph, at = inp.phase, inp.at_engage
    n1c = inp.n1_cmd_pct
    pla = inp.pla_deg[0]
    d_n1c = np.r_[0.0, np.diff(n1c)]
    d_pla = np.r_[0.0, np.abs(np.diff(pla))]
    running = np.all(inp.pla_deg > 15.0, axis=0)  # every lever above cutoff
    ok_at = (at == 1) & np.isin(ph, (4, 5, 6)) & (n1c >= N1C_MIN) & running
    ok_man = (at == 0) & np.isin(ph, (6, 7)) & (inp.wow == 1) & running  # DASHlink WOW = 1 is airborne
    best_at = None
    L = round(AT_S * RATE)
    for a, b in runs(ok_at):
        if b - a < L:
            continue
        w = _best_window(a, b, np.abs(d_n1c), L)
        seg = d_n1c[w[0] : w[1]]
        if seg[seg > 0].sum() >= AT_MIN_DIR and -seg[seg < 0].sum() >= AT_MIN_DIR:
            if best_at is None or w[2] > best_at[2]:
                best_at = w
    best_man = None
    for a, b in runs(ok_man):
        if b - a < MAN_MIN_S * RATE:
            continue
        w = _best_window(a, b, d_pla, round(MAN_S * RATE))
        if w[2] >= MAN_MIN_SCORE and (best_man is None or w[2] > best_man[2]):
            best_man = w
    return {"at": best_at, "man": best_man}


def main(mat_dir: str, out: str, n_scan: int = 12) -> None:
    picked: dict[str, list[dict]] = {"at": [], "man": []}
    for fname in flight_order()[:n_scan]:
        s = scan(mat_dir, fname)
        for kind, nmax in (("at", N_AT), ("man", N_MAN)):
            w = s[kind]
            if w is not None and len(picked[kind]) < nmax:
                picked[kind].append(
                    {"flight": fname, "a": int(w[0]), "b": int(w[1]), "score": round(w[2], 2)}
                )
    res = {"n_scan": n_scan, "at_s": AT_S, "man_s": MAN_S, "n1c_min": N1C_MIN, **picked}
    with open(out, "w") as fh:
        json.dump(res, fh, indent=1)
    for kind in ("at", "man"):
        for w in picked[kind]:
            print(kind, w["flight"], w["a"], w["b"], (w["b"] - w["a"]) / RATE, "s", "score", w["score"])


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], *(int(x) for x in sys.argv[3:4]))
