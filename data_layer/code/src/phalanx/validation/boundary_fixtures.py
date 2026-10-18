"""Boundary fixtures: flights and PLA traces placed exactly on the battery's thresholds (CONTROL FIXTURE).

**CONTROL FIXTURE, NOT A MODEL.** The full control flights of `testing.py` sit far from every threshold
(thousands of airborne samples, steps of 6-12 deg), so changing a threshold by one sample or a fraction of an
LSB
leaves their statistics unchanged: such a mutation survives `make check`. Each fixture here sits *on* one
threshold, usually with one case just inside and one just outside, so the original round-2 code and the port
must
agree on which side every case falls (`golden/make_round2_boundaries.py`,
`tests/golden/test_validation_boundaries_golden.py`).

| Fixture | Threshold pinned (round-2 source) |
|---|---|
| `air600` / `air599` | B1/B2 minimum 600 airborne samples (`battery.b1_stats`, `b2_stats`) |
| `b5_597` / `b5_596` | B5 minimum 150 decimated samples (`battery.b5_moments`) |
| `run2400` / `run2399` | B3 (i) longest airborne run >= 600 s (`battery.longest_air_run`) |
| `seg480` / `seg479` | B4 airborne segment >= 120 s (`battery.b4_granger`); constant EGT: F floor 1e-6, rss
= 0 |
| `ph40` | B6 phase with 40 airborne samples kept, 39 missing (`battery.b6_stats`) |
| `n1_edge` | airborne rule N1 > 25 % (25.0 not airborne, 25.03125 airborne: one recorder LSB) |
| `lag_edge` | B2 +-10 s window (true lags 39, 40, 41 samples) |
| `steps_edge` | B3 (ii): |dPLA| >= 5 deg, |D| >= 5 LSB per family, 5-s pre / 30-s post windows, R^2 > 0.9 |
| `pla_traces()` | round-1 `transients.find_steps` literals (jump, pre/post ptp, onset, window lengths, skip,
bounds) |
| `mach_trace()` | round-2 `r2common._clean_mach` (window k = 9, threshold 0.15) |

Bit reproducibility: inputs use only the raw PCG64 stream and correctly rounded IEEE operations in a fixed
order
(as `testing.py`); thresholds are hit with dyadic values, so comparisons at the boundary are exact.
"""

from __future__ import annotations

import numpy as np

from phalanx.validation.flightdata import DASHLINK_UNITS, FlightRecord
from phalanx.validation.testing import LSB, _Bits

__all__ = [
    "BOUNDARY_FLIGHTS",
    "R2_WIGGLE",
    "boundary_flight",
    "mach_trace",
    "pla_traces",
]

FAM = ("N1", "N2", "EGT", "FF")
BASE = {"N1": 60.0, "N2": 80.0, "EGT": 500.0, "FF": 2000.0}
WALK = {"N1": 0.25, "N2": 0.25, "EGT": 2.0, "FF": 16.0}
#: wiggle amplitudes (fraction of the step) that put the B3 (ii) fit R^2 just above 0.9 (accel 0.9021, decel
# 0.9008)
#: and just below (0.8991, 0.8978); measured with scipy 1.18, drift between scipy versions ~1e-6
R2_WIGGLE = {"above": 0.117, "below": 0.119}


def _walk(bits: _Bits, n: int, start: float, scale: float) -> list[float]:
    out, x = [], start
    for u in bits.uniform(n):
        x = x + scale * (u - 0.5)
        out.append(x)
    return out


def _quant(x: list[float], lsb: float) -> list[float]:
    return [float(np.rint(v / lsb)) * lsb for v in x]


def _default(name: str, n: int) -> dict[str, list[list[float]]]:
    """Random-walk outputs per family and engine (quantised to the recorder lattice)."""
    out: dict[str, list[list[float]]] = {}
    for f in FAM:
        out[f] = []
        for e in range(4):
            b = _Bits("bnd", name, f, e)
            out[f].append(_quant(_walk(b, n, BASE[f], WALK[f]), LSB[f]))
    return out


def _record(name: str, Y, pla=None, phase=None) -> FlightRecord:
    n = len(Y["N1"][0])
    b = _Bits("bnd", name, "inputs")
    u = b.uniform(2 * n)
    theta = [0.85 + 0.125 * u[k] for k in range(n)]
    delta = [0.3 + 0.5 * u[n + k] for k in range(n)]
    return FlightRecord(
        flight_id=f"bnd_{name}",
        rate_hz=4.0,
        outputs={f: np.array(Y[f], float) for f in FAM},
        pla=np.array(pla if pla is not None else [[60.0 + 0.125 * e] * n for e in range(4)], float),
        theta=np.array(theta, float),
        delta=np.array(delta, float),
        phase=np.array(phase if phase is not None else [5] * n, np.int64),
        units=DASHLINK_UNITS,
        meta={"source": "CONTROL FIXTURE (boundary)", "fixture": name},
    )


def _ground(Y, air: list[bool]) -> None:
    """Make non-airborne samples fail the airborne rule (engine 1 N1 = 20 %)."""
    for k, a in enumerate(air):
        if not a:
            Y["N1"][0][k] = 20.0


def _air_count(name: str, n: int, n_air: int) -> FlightRecord:
    Y = _default(name, n)
    _ground(Y, [k < n_air for k in range(n)])
    return _record(name, Y)


def _air_run(name: str, n: int, runs: list[tuple[int, int]], constant_egt: bool = False) -> FlightRecord:
    Y = _default(name, n)
    _ground(Y, [any(a <= k < b for a, b in runs) for k in range(n)])
    if constant_egt:
        Y["EGT"][0] = [500.0] * n
    return _record(name, Y)


def _ph40() -> FlightRecord:
    n = 1000
    ph = [5] * n
    for k in range(100, 140):
        ph[k] = 4  # 40 airborne samples: kept
    for k in range(200, 239):
        ph[k] = 6  # 39: missing
    return _record("ph40", _default("ph40", n), phase=ph)


def _n1_edge() -> FlightRecord:
    n = 1000
    Y = _default("n1_edge", n)
    for k in range(n):
        Y["N1"][0][k] = max(Y["N1"][0][k], 40.0)
    for k in range(100, 400):
        Y["N1"][2][k] = 25.0  # not airborne (rule is N1 > 25)
    for k in range(500, 800):
        Y["N1"][1][k] = 25.03125  # airborne (one recorder LSB above)
    return _record("n1_edge", Y)


def _lag_edge() -> FlightRecord:
    n = 2000
    Y = _default("lag_edge", n)
    ff = Y["FF"][0]

    def shifted(d: int, base: float, div: float) -> list[float]:
        return [base + (ff[max(k - d, 0)] - 2000.0) / div for k in range(n)]

    Y["N2"][0] = shifted(40, 80.0, 128.0)  # FF -> N2 lag exactly 10 s: inside the window
    Y["N1"][0] = shifted(41, 60.0, 128.0)  # FF -> N1 lag 10.25 s: just outside
    Y["EGT"][0] = shifted(39, 500.0, 16.0)  # FF -> EGT lag 9.75 s
    return _record("lag_edge", Y)


# ---------------------------------------------------------------- B3 (ii) steps
_S = (400, 900, 1300)  # step onsets: +5 deg (kept), +4.9907 deg (dropped), -5 deg (kept)


def _steps_pla(n: int) -> list[list[float]]:
    row = []
    for k in range(n):
        if k < _S[0]:
            v = 40.0
        elif k < _S[1]:
            v = 45.0
        elif k < _S[2]:
            v = 50.0
            if k == _S[1] + 100:
                v = 49.0  # post mean 50 - 1/108: |dPLA| = 4.9907 < 5
        else:
            v = 45.0
        row.append(v)
    return [list(row) for _ in range(4)]


def _lag_to(target: list[float], tau_samples: float) -> list[float]:
    a = 1.0 / tau_samples
    out, y = [], target[0]
    for t in target:
        y = y + a * (t - y)
        out.append(y)
    return out


def _response(
    n: int, base: float, steps_lsb: tuple[float, float, float], lsb: float, quant: bool
) -> list[float]:
    tgt, level = [], base
    for k in range(n):
        for s, d in zip(_S, steps_lsb, strict=True):
            if k == s:
                level = level + d * lsb
        tgt.append(level)
    y = _lag_to(tgt, 4.0)
    return _quant(y, lsb) if quant else y


def _steps_edge() -> FlightRecord:
    n = 1600
    Y = _default("steps_edge", n)
    s1 = _S[0]
    for e in range(4):
        for f in ("N1", "FF", "EGT"):
            Y[f][e] = _response(n, BASE[f], (5.0, 20.0, -5.0), LSB[f], quant=True)
    # engine 2: one late sample at +4 LSB in the final-value window [s+100, s+120): D = 4.95 LSB (dropped)
    for f in ("N1", "FF", "EGT"):
        Y[f][1][s1 + 110] = Y[f][1][s1 + 110] - LSB[f]
    # engine 3: pre/post window edges
    Y["N1"][2][s1 - 21] += LSB["N1"]  # outside the 5-s pre window: kept (a 21-sample window would drop it)
    Y["EGT"][2][s1 - 20] += LSB["EGT"]  # inside: D = 4.95 LSB, dropped (a 19-sample window would keep it)
    Y["FF"][2][s1 + 99] -= LSB["FF"]  # just before the final-value window: kept
    Y["FF"][2][s1 + 120] -= LSB["FF"]  # just after the 30-s window: kept
    # engine 4: R^2 just above (FF) and just below (N1) 0.9: unfittable alternating wiggle on a 50-LSB step
    for f, which in (("FF", "above"), ("N1", "below")):
        y = _response(n, BASE[f], (50.0, 50.0, -50.0), LSB[f], quant=False)
        c = R2_WIGGLE[which] * 50.0 * LSB[f]
        Y[f][3] = [v + (c if k % 2 else -c) for k, v in enumerate(y)]
    return _record("steps_edge", Y, pla=_steps_pla(n))


BOUNDARY_FLIGHTS: dict[str, object] = {
    "air600": lambda: _air_count("air600", 1000, 600),
    "air599": lambda: _air_count("air599", 1000, 599),
    "b5_597": lambda: _air_count("b5_597", 1000, 597),
    "b5_596": lambda: _air_count("b5_596", 1000, 596),
    "run2400": lambda: _air_run("run2400", 2600, [(100, 2500)]),
    "run2399": lambda: _air_run("run2399", 2600, [(100, 2499)]),
    "seg480": lambda: _air_run("seg480", 1400, [(100, 580), (700, 1179)], constant_egt=True),
    "seg479": lambda: _air_run("seg479", 1400, [(100, 579), (700, 1179)], constant_egt=True),
    "ph40": _ph40,
    "n1_edge": _n1_edge,
    "lag_edge": _lag_edge,
    "steps_edge": _steps_edge,
}


def boundary_flight(name: str) -> FlightRecord:
    """One boundary fixture flight by name (see the module table)."""
    return BOUNDARY_FLIGHTS[name]()  # type: ignore[operator]


# ---------------------------------------------------------------- find_steps traces
_D = 2.0**-10  # dyadic offset: boundaries are hit exactly


def _flat(level: float, k: int) -> list[float]:
    return [level] * k


def _ramp(level: float, k: int) -> list[float]:
    """Post-step plateau with a slow dyadic ramp (ptp < 1.5) so that every window shift changes its mean."""
    return [level + j * 2.0**-7 for j in range(k)]


def pla_traces() -> dict[str, np.ndarray]:
    """PLA traces for `find_steps`, each event just inside or just outside one rule (dyadic values)."""
    T: dict[str, list[float]] = {}
    for d in (-1, 0, 1):
        tag = {-1: "m", 0: "0", 1: "p"}[d]
        # jump of 5 + d/1024 within 2 s (detected iff >= 5); flat plateau so no later scan position
        # re-triggers
        T[f"jump_{tag}"] = _flat(40.0, 300) + _flat(45.0 + d * _D, 300)
        # pre-window range 1 + d/1024 (detected iff <= 1): outlier inside every candidate window
        pre = _flat(40.0, 300)
        pre[290] = 41.0 + d * _D
        T[f"pre_ptp_{tag}"] = pre + _ramp(47.0, 200) + _flat(47.0, 100)
        # post-window range 1.5 + d/1024 (detected iff <= 1.5)
        post = _flat(47.0, 200)
        post[50] = 48.5 + d * _D
        T[f"post_ptp_{tag}"] = _flat(40.0, 300) + post + _flat(47.0, 100)
        # onset tolerance 0.5 + d/1024: one intermediate sample before the jump
        T[f"onset_{tag}"] = [*_flat(40.0, 300), 40.5 + d * _D, *_ramp(46.0, 200), *_flat(46.0, 100)]
    # window lengths: outlier 41 / 40 samples before the trigger (pre window is [i - 40, i])
    for off, tag in ((49, "out"), (48, "in")):
        tr = _flat(40.0, 300)
        tr[300 - off] = 42.0
        T[f"prewin_{tag}"] = tr + _ramp(46.0, 200) + _flat(46.0, 100)
    # post-window start/end (outliers at i + 11 / i + 12 and i + 119 / i + 120, trigger i = s - 8)
    for pos, tag in ((3, "start_out"), (4, "start_in"), (111, "end_in"), (112, "end_out")):
        post = _ramp(46.0, 200)
        post[pos] = 49.0
        T[f"postwin_{tag}"] = _flat(40.0, 300) + post + _flat(46.0, 100)
    # skip of 30 s after a detection: second step 120 / 119 samples after the first
    for gap, tag in ((120, "120"), (119, "119")):
        T[f"skip_{tag}"] = _flat(40.0, 300) + _ramp(46.0, gap) + _ramp(52.0, 200) + _flat(52.0, 100)
    # scan start (i from 40) and end (i < n - 124): steps at the first and last scanned triggers
    # jump spacing (2 s = 8 samples): a slowly ramping pre-step level, so a one-sample trigger shift moves pm
    T["spacing"] = [40.0 + k * 2.0**-9 for k in range(300)] + _ramp(47.0, 200) + _flat(47.0, 100)
    T["start_edge"] = _flat(40.0, 48) + _ramp(46.0, 200) + _flat(46.0, 100)
    T["start_minus"] = _flat(40.0, 47) + _ramp(46.0, 200) + _flat(46.0, 100)
    for last, tag in ((117, "in"), (116, "out")):
        T[f"end_{tag}"] = _flat(40.0, 400) + _ramp(46.0, last)
    return {k: np.array(v, float) for k, v in T.items()}


def mach_trace() -> np.ndarray:
    """MACH with zeros at the edges of round-2 `_clean_mach` (2-s window, median > 0.15)."""
    m = [0.0] * 50 + [0.3] * 750  # ground zeros at the start: kept
    m[100] = 0.0  # isolated in-flight zero: interpolated
    for k in range(291, 310):
        m[k] = 0.15  # neighbourhood median exactly 0.15: not > 0.15, kept
    m[300] = 0.0
    for k in range(391, 410):
        m[k] = 0.15 + 2.0**-20  # just above: interpolated
    m[400] = 0.0
    for k in range(596, 605):
        m[k] = 0.0  # 9 zeros: median of 19 samples is 0.3, of 17 samples would be 0
    m[-1] = 0.0  # trailing zero next to cruise values
    return np.array(m, float)


# ---------------------------------------------------------------- evaluation-layer boundaries
#: B3 (ii) step rows (response, direction, tau) of two 2-flight groups. Group A has cells with exactly 3 steps
#: (median kept) and exactly 2 steps (NaN); group B has 3 or 4 per cell (pins STEP_MIN_PER_CELL = 3).
STEP_GROUPS: dict[str, list[list[tuple[float, float, float]]]] = {
    "A": [
        [(0, 0, 1.0), (0, 0, 2.0), (0, 1, 1.5), (1, 0, 0.75), (2, 1, 4.0)],
        [(0, 0, 3.0), (0, 1, 2.5), (1, 0, 1.125), (1, 0, 1.25), (2, 1, 4.5)],
    ],
    "B": [
        [(0, 0, 1.5), (0, 0, 2.5), (0, 1, 3.0), (0, 1, 2.0), (1, 0, 1.0), (2, 1, 5.0), (2, 1, 3.5)],
        [(0, 0, 2.25), (0, 1, 2.75), (1, 0, 0.875), (1, 0, 1.375), (1, 0, 1.0), (2, 1, 4.25), (1, 1, 2.0)],
    ],
}

#: verdict patterns for the decision rule (B1..B6) and the G0 result: GO needs no FAIL and >= 4 PASS
DECISION_PATTERNS: dict[str, tuple[tuple[str, ...], bool]] = {
    "4pass_2inc": (("PASS", "PASS", "PASS", "PASS", "INCONCLUSIVE", "INCONCLUSIVE"), True),
    "3pass_3inc": (("PASS", "PASS", "PASS", "INCONCLUSIVE", "INCONCLUSIVE", "INCONCLUSIVE"), True),
    "5pass_1fail": (("PASS", "PASS", "PASS", "PASS", "PASS", "FAIL"), True),
    "6pass_g0fail": (("PASS",) * 6, False),
}


# ---------------------------------------------------------------- G0 metadata boundaries
def gate0_boundary_channels() -> tuple[dict[str, tuple[np.ndarray, float]], int, int]:
    """Recorded-file stand-in (round-1 `config.GROUP` order) whose values sit on G0 feature thresholds:
    lattice fractions 2^-10 (< 1e-3, on lattice) and 2^-10 + 2^-13 (> 1e-3, off); values 0.97e-6 and
    1.05e-6 from a sentinel at 0 (tolerance 1e-6); value/LSB fractions on the histogram bin edges."""
    n = 400
    ch: dict[str, tuple[np.ndarray, float]] = {}
    for f in ("N1", "N2", "EGT", "FF"):
        for k in range(1, 5):
            b = _Bits("g0bnd", f, k)
            base = [BASE[f] + LSB[f] * float(int(u * 64)) for u in b.uniform(n)]
            ch[f"{f}_{k}"] = (np.array(base, np.float32), 4.0)
    lsb = LSB["N1"]
    fr = [2.0**-10, 2.0**-10 + 2.0**-13, -(2.0**-10), -(2.0**-10 + 2.0**-13), 0.25, -0.375]
    ch["N1_1"] = (np.array([(60.0 / lsb + float(j) + fr[j % 6]) * lsb for j in range(n)], np.float64), 4.0)
    ff = [0.97e-6, 1.05e-6, -0.97e-6, -1.05e-6] * 10 + [2000.0] * (n - 40)
    ch["FF_1"] = (np.array(ff, np.float64), 4.0)
    edges = [(-0.5 + 0.1 * m) * 0.5 for m in range(11)]
    ch["EGT_3"] = (np.array([500.0 + edges[j % 11] for j in range(n)], np.float64), 4.0)
    code = np.array([1 + int(u * 4000) for u in _Bits("g0bnd", "VRTG").uniform(2 * n)], float)
    vrtg = (code.astype(np.float32) * np.float32(0.0010508) + np.float32(-3.3761)).astype(np.float32)
    ch["VRTG"] = (vrtg, 8.0)
    return ch, n // 4, n // 4


# ---------------------------------------------------------------- DASHlink adapter boundaries
def adapter_inputs() -> dict[str, np.ndarray]:
    """ALT [ft], MACH, TAT [degC] spanning the ISA tropopause (36,089 ft) and the MACH-cleaning cases."""
    alt = np.array([0.0, 1000.0, 20000.0, 36088.5, 36089.0, 36089.5, 40000.0, 45000.0] * 100, float)
    tat = np.array([15.0, 0.0, -30.0, -56.5, -56.5, -56.5, -45.0, -40.0] * 100, float)
    return {"alt": alt, "mach": mach_trace(), "tat": tat}


def write_mat(path: str) -> None:
    """A small DASHlink-layout MAT file (structs with data / Rate / Units) for the adapter golden test.
    Channel lengths differ on purpose (n = min rule); TAT, PH and WOW are 1 Hz."""
    import scipy.io as sio

    n4 = 1204
    d: dict[str, dict[str, object]] = {}
    for f in FAM:
        for k in range(1, 5):
            x = _quant(_walk(_Bits("mat", f, k), n4 + k % 2, BASE[f], WALK[f]), LSB[f])
            dt = np.float64 if f == "FF" else np.float32
            d[f"{f}_{k}"] = {"data": np.array(x, dt), "Rate": 4.0, "Units": ""}
    for k in range(1, 5):
        d[f"PLA_{k}"] = {
            "data": np.array(_walk(_Bits("mat", "PLA", k), n4, 60.0, 0.5), np.float32),
            "Rate": 4.0,
        }
    m = mach_trace()
    d["MACH"] = {"data": np.concatenate([m, m[: n4 + 1 - m.size]]).astype(np.float32), "Rate": 4.0}
    d["ALT"] = {"data": np.array(_walk(_Bits("mat", "ALT"), n4 + 2, 30000.0, 400.0), np.float32), "Rate": 4.0}
    n1 = n4 // 4 + 1
    d["TAT"] = {"data": np.array(_walk(_Bits("mat", "TAT"), n1, -40.0, 1.0), np.float32), "Rate": 1.0}
    d["PH"] = {"data": np.array([1 + (k * 7) // n1 for k in range(n1)], np.float64), "Rate": 1.0}
    d["WOW"] = {"data": np.array([0] * 20 + [1] * (n1 - 40) + [0] * 20, np.float64), "Rate": 1.0}
    d["FRMC"] = {"data": np.arange(n4 // 16, dtype=np.float64), "Rate": 0.25}
    sio.savemat(str(path), d)
