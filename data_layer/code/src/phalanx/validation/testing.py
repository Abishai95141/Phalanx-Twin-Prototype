"""Harness self-test fixtures: control flights and negative-control operators (M20 "the harness validates
itself").

**CONTROL FIXTURE, NOT A MODEL.** `control_flight` produces flights from a toy coupled engine chain so that
the
battery can be tested without real data: golden old-vs-new reproduction (A2) and negative controls (A3). It is
never a data source for the deliverable path, it is not calibrated to DASHlink, and its parameters carry no
evidence tag. The real-data versions of these checks run on DASHlink (pytest marker `data`).

Bit reproducibility: the generator uses only the raw PCG64 bit stream (stable across NumPy versions) and
correctly rounded IEEE-754 operations (+, -, *, /, sqrt, rint) in a fixed order, in plain Python floats. The
same identity therefore gives bit-identical arrays in the round-2 environment and in the build environment;
`fixture_sha256` lets a test confirm that before comparing estimator outputs.

Toy chain per engine k (4 Hz, dt = 0.25 s, 1200-s flight), driven by per-engine PLA and a shared profile:
  disturbance  w_k = common AR(1) + unit AR(1)             (process disturbance entering the dynamics)
  fuel         Wf_k: first-order lag to Wcmd(PLA_k) * delta * sqrt(theta) * (1 + w_k)
  core         N2_k: lag to sqrt(theta) * g(Wf / (delta sqrt(theta))) + core disturbance
  fan          N1_k: lag to sqrt(theta) * h(N2 / sqrt(theta)) + fan disturbance
  EGT          EGT_k: lag to theta^a * k(Wfc, N1c) - 273.15 (a in {0.5, 0.75}, via sqrt only)
  measured     FF = lagged Wf; every output quantised to the DASHlink recorder lattice.
Negative-control operators break exactly one behaviour of a record: fast-band coupling (`decouple_fast_band`)
or lead-lag order (`delay_family`); `dither_requantise` adds excess sensor-independent noise at the LSB level.
"""

from __future__ import annotations

import hashlib
import math
import zlib
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from phalanx.validation.battery.filters import lowpass
from phalanx.validation.flightdata import DASHLINK_UNITS, FlightRecord

__all__ = [
    "PARTNER_TAIL",
    "REFERENCE_TAIL",
    "STANDIN_AFFINE",
    "STANDIN_LSB",
    "STANDIN_SENTINELS",
    "ToyTail",
    "control_flight",
    "decouple_fast_band",
    "delay_family",
    "dither_requantise",
    "double_quantise",
    "fixture_sha256",
    "g0_control_matrices",
    "gate0_standin",
]

RATE = 4.0
DT = 0.25
LSB = {"N1": 0.03125, "N2": 0.03125, "EGT": 0.5, "FF": 8.0}
_ENTROPY = 0x5048414C414E58  # "PHALANX": fixed root entropy of the control fixtures


@dataclass(frozen=True)
class ToyTail:
    """Parameters of one toy tail (control fixture only; no evidence tag, not a model of any engine)."""

    name: str
    tau_f: float = 0.5
    tau_ffs: float = 0.25
    tau_2: float = 1.5
    tau_1: float = 1.0
    tau_t: float = 3.0
    n1_slope: float = 1.40
    egt_gain: float = 300.0
    egt_sqrt_only: bool = False  # theta^0.5 instead of theta^0.75
    sig_common: float = 0.010
    sig_unit: float = 0.012
    sig_core: float = 0.06
    sig_fan: float = 0.08


REFERENCE_TAIL = ToyTail(name="toy_ref")
PARTNER_TAIL = ToyTail(
    name="toy_partner",
    tau_f=0.65,
    tau_ffs=0.35,
    tau_2=1.9,
    tau_1=1.3,
    tau_t=3.8,
    n1_slope=1.36,
    egt_gain=330.0,
    egt_sqrt_only=True,
    sig_common=0.014,
    sig_unit=0.009,
    sig_core=0.09,
    sig_fan=0.05,
)


class _Bits:
    """Uniforms in [0, 1) from the raw PCG64 stream: (raw >> 11) * 2^-53 (exact, version-stable)."""

    def __init__(self, *key: str | int) -> None:
        sk = tuple(zlib.crc32(str(k).encode()) & 0xFFFFFFFF for k in key)
        self._bg = np.random.PCG64(np.random.SeedSequence(_ENTROPY, spawn_key=sk))

    def uniform(self, n: int) -> list[float]:
        raw = self._bg.random_raw(n)
        return [float(int(r) >> 11) * (2.0**-53) for r in raw]

    def normal(self, n: int) -> list[float]:
        """Approximately standard normal: (sum of 4 uniforms - 2) * sqrt(3), added left to right."""
        u = self.uniform(4 * n)
        s3 = math.sqrt(3.0)
        return [(((u[4 * i] + u[4 * i + 1]) + u[4 * i + 2]) + u[4 * i + 3] - 2.0) * s3 for i in range(n)]


def _q(x: list[float], lsb: float) -> list[float]:
    return [float(np.rint(v / lsb)) * lsb for v in x]


#: Toy flight phases: (start [s], end [s], DASHlink PH code, PLA level [deg]); 1200 s in total.
_PHASES: tuple[tuple[float, float, int, float], ...] = (
    (0.0, 60.0, 2, 22.0),
    (60.0, 120.0, 3, 75.0),
    (120.0, 420.0, 4, 68.0),
    (420.0, 960.0, 5, 58.0),
    (960.0, 1140.0, 6, 40.0),
    (1140.0, 1200.0, 7, 22.0),
)
N_SAMPLES = 4800


def _phase_at(t: float) -> tuple[int, int, float]:
    for j, (a, b, ph, pla) in enumerate(_PHASES):
        if a <= t < b:
            return j, ph, pla
    return len(_PHASES) - 1, _PHASES[-1][2], _PHASES[-1][3]


def _profile(n: int) -> tuple[list[float], list[float], list[int]]:
    """Altitude [ft], Mach and phase code of the toy flight at 4 Hz (piecewise linear)."""
    alt, mach, ph = [], [], []
    for i in range(n):
        t = i * DT
        j, p, _ = _phase_at(t)
        a0, b0 = _PHASES[j][0], _PHASES[j][1]
        f = (t - a0) / (b0 - a0)
        if p == 2:
            a, m = 0.0, 0.0
        elif p == 3:
            a, m = 0.0, 0.25 * f
        elif p == 4:
            a, m = 30000.0 * f, 0.25 + 0.5 * f
        elif p == 5:
            a, m = 30000.0, 0.75
        elif p == 6:
            a, m = 30000.0 * (1.0 - f), 0.75 - 0.5 * f
        else:
            a, m = 0.0, 0.25 * (1.0 - f)
        alt.append(a)
        mach.append(m)
        ph.append(p)
    return alt, mach, ph


def _pla_schedule(n: int, flight: int) -> list[list[float]]:
    """Per-engine PLA [deg]: phase levels, four flight-specific 40-s steps of 6-12 deg, common trims."""
    bits = _Bits("pla", flight)
    lv = bits.uniform(12)
    trims = bits.uniform(n // 40 + 2)
    steps = (180.0 + 60.0 * lv[0], 480.0 + 80.0 * lv[1], 720.0 + 80.0 * lv[2], 1000.0 + 40.0 * lv[3])
    amps = [6.0 + 6.0 * v for v in lv[4:8]]
    signs = [1.0 if v < 0.5 else -1.0 for v in lv[8:12]]
    out = []
    for e in range(4):
        row = []
        for i in range(n):
            t = i * DT
            _, p, base = _phase_at(t)
            for j, ts in enumerate(steps):
                if ts <= t < ts + 40.0:
                    base = base + amps[j] * signs[j]
            trim = 0.4 * (trims[i // 40] - 0.5) if p == 5 else 0.0  # autothrottle-like trim, held 10 s
            row.append(base + trim + 0.1 * e)
        out.append(row)
    return out


def control_flight(flight: int, tail: ToyTail = REFERENCE_TAIL, version: str = "real") -> FlightRecord:
    """One toy control flight (CONTROL FIXTURE, not a model).

    Args:
        flight: flight index; fixes the inputs (PLA schedule, profile) so that versions are paired.
        tail: toy tail parameters (REFERENCE_TAIL or PARTNER_TAIL, or a custom ToyTail).
        version: disturbance-stream label; two versions of a flight share inputs and differ only in the
            process-disturbance realisation (a "replicate" of the same flight).
    """
    n = N_SAMPLES
    alt, mach, ph = _profile(n)
    pla = _pla_schedule(n, flight)
    theta = [1.0 - 0.2 * (a / 36000.0) + 0.04 * m * m for a, m in zip(alt, mach, strict=True)]
    delta = [(1.0 - a / 50000.0) * (1.0 + 0.7 * m * m) for a, m in zip(alt, mach, strict=True)]
    sq = [math.sqrt(t) for t in theta]
    bits_c = _Bits("dist", tail.name, flight, version, "common")
    wc = bits_c.normal(n)
    out = {f: [] for f in ("N1", "N2", "EGT", "FF")}
    a_f, a_ffs = DT / tail.tau_f, DT / tail.tau_ffs
    a_2, a_1, a_t = DT / tail.tau_2, DT / tail.tau_1, DT / tail.tau_t
    for e in range(4):
        b = _Bits("dist", tail.name, flight, version, "unit", e)
        wu, wcore, wfan = b.normal(n), b.normal(n), b.normal(n)
        dc = du = dcore = dfan = 0.0
        wf = ffm = None
        n2 = n1 = egt = None
        rows = {f: [] for f in out}
        for i in range(n):
            dc = 0.95 * dc + tail.sig_common * wc[i]
            du = 0.90 * du + tail.sig_unit * wu[i]
            dcore = 0.80 * dcore + tail.sig_core * wcore[i]
            dfan = 0.80 * dfan + tail.sig_fan * wfan[i]
            ds = delta[i] * sq[i]
            wcmd = (200.0 + 40.0 * (pla[e][i] - 20.0)) * ds * (1.0 + (dc + du))
            wf = wcmd if wf is None else wf + (wcmd - wf) * a_f
            wfc = wf / ds
            u = wfc / 2000.0
            n2t = sq[i] * (55.0 + 45.0 * u - 8.0 * u * u) + dcore
            n2 = n2t if n2 is None else n2 + (n2t - n2) * a_2
            n1t = sq[i] * (-40.0 + tail.n1_slope * (n2 / sq[i])) + dfan
            n1 = n1t if n1 is None else n1 + (n1t - n1) * a_1
            n1c = n1 / sq[i]
            th_a = sq[i] if tail.egt_sqrt_only else sq[i] * math.sqrt(sq[i])
            egtt = (550.0 + tail.egt_gain * u + 1.5 * (n1c - 60.0)) * th_a - 273.15
            egt = egtt if egt is None else egt + (egtt - egt) * a_t
            ffm = wf if ffm is None else ffm + (wf - ffm) * a_ffs
            rows["N1"].append(n1)
            rows["N2"].append(n2)
            rows["EGT"].append(egt)
            rows["FF"].append(ffm)
        for f in out:
            out[f].append(_q(rows[f], LSB[f]))
    return FlightRecord(
        flight_id=f"ctrl{flight:03d}",
        rate_hz=RATE,
        outputs={f: np.array(v, float) for f, v in out.items()},
        pla=np.array(pla, float),
        theta=np.array(theta, float),
        delta=np.array(delta, float),
        phase=np.array(ph, np.int64),
        units=DASHLINK_UNITS,
        meta={"source": "CONTROL FIXTURE (toy chain, not a model)", "tail": tail.name, "version": version},
    )


def fixture_sha256(rec: FlightRecord) -> str:
    """SHA-256 over the record's arrays (outputs in family order, PLA, theta, delta, phase)."""
    h = hashlib.sha256()
    for f in sorted(rec.outputs):
        h.update(f.encode())
        h.update(np.ascontiguousarray(rec.outputs[f], dtype="<f8").tobytes())
    for a in (rec.pla, rec.theta, rec.delta):
        h.update(np.ascontiguousarray(a, dtype="<f8").tobytes())
    h.update(np.ascontiguousarray(rec.phase, dtype="<i8").tobytes())
    return h.hexdigest()


# ---------------------------------------------------------------- negative-control operators
def decouple_fast_band(
    rec: FlightRecord, key: Sequence[str | int] = ("decouple",), fc: float = 0.2
) -> FlightRecord:
    """Replace each channel's fast band (x - lowpass 0.2 Hz) by a circularly shifted copy of itself, with an
    independent shift per channel. Marginals and spectra are kept; cross-channel fast coupling is destroyed
    (the 'independent per-channel noise standing in for coupled dynamics' failure, round-1 correlation check).
    """
    bits = _Bits("op", *key, rec.flight_id)
    outs = {}
    for f in sorted(rec.outputs):
        X = np.array(rec.outputs[f], float)
        for k in range(X.shape[0]):
            slow = lowpass(X[k], rec.rate_hz, fc)
            shift = 400 + int(bits.uniform(1)[0] * (X.shape[1] - 800))
            X[k] = slow + np.roll(X[k] - slow, shift)
        outs[f] = X
    return rec.replace_outputs(outs, control="decouple_fast_band")


def delay_family(rec: FlightRecord, family: str, seconds: float) -> FlightRecord:
    """Delay one output family by `seconds` (hold the first value): breaks the lead-lag order only."""
    s = round(seconds * rec.rate_hz)
    outs = {}
    for f, X in rec.outputs.items():
        X = np.array(X, float)
        if f == family and s > 0:
            X = np.concatenate([np.repeat(X[:, :1], s, axis=1), X[:, :-s]], axis=1)
        outs[f] = X
    return rec.replace_outputs(outs, control=f"delay_{family}_{seconds}s")


def dither_requantise(
    rec: FlightRecord, lsb: dict[str, float] | None = None, key: Sequence[str | int] = ("dither",)
) -> FlightRecord:
    """Add independent uniform dither on [-1, +1) LSB per sample and re-quantise to the recorder lattice, so
    that
    about half of the samples move by one LSB: excess sensor-independent noise at the LSB level.
    (A +-0.5 LSB dither would round lattice values back to themselves.) Measured on the DASHlink s20 batch:
    B1, B3 (i) and B4 FAIL, because the real fast band is quantisation-dominated (round-2 REPORT §3.5)."""
    lsb = lsb or LSB
    bits = _Bits("op", *key, rec.flight_id)
    outs = {}
    for f in sorted(rec.outputs):
        X = np.array(rec.outputs[f], float)
        u = 2.0 * np.array(bits.uniform(X.size), float).reshape(X.shape) - 1.0
        outs[f] = np.rint((X + u * lsb[f]) / lsb[f]) * lsb[f]
    return rec.replace_outputs(outs, control="dither_requantise")


def double_quantise(
    rec: FlightRecord, native: dict[str, float], lsb: dict[str, float] | None = None
) -> FlightRecord:
    """Re-quantise outputs through a native step, then the recorder lattice (AD-05 form):
    y = LSB_rec * rint(LSB_nat * rint(x / LSB_nat) / LSB_rec). Families absent from `native` keep a single
    lattice. Used as the reference texture in the G1 negative control."""
    lsb = lsb or LSB
    outs = {}
    for f in sorted(rec.outputs):
        X = np.array(rec.outputs[f], float)
        if f in native:
            X = lsb[f] * np.rint(native[f] * np.rint(X / native[f]) / lsb[f])
        outs[f] = X
    return rec.replace_outputs(outs, control="double_quantise")


# ---------------------------------------------------------------- G0 stand-ins (shared with the golden
# generator)
#: Sentinel, LSB and VRTG lattice tables of the G0 recorded-file stand-in (fixture values, not measurements).
STANDIN_SENTINELS: dict[str, list[float]] = {"FF_1": [0.0], "EGT_2": [0.0], "VRTG": [-3.375]}
STANDIN_LSB: dict[str, float] = {
    **{f"{f}_{k}": v for f, v in LSB.items() for k in (1, 2, 3, 4)},
    "VRTG": 0.00105,
}
STANDIN_AFFINE: dict[str, tuple[float, float]] = {"VRTG": (0.0010508, -3.3761)}
_STANDIN_ORDER = tuple(f"{f}_{k}" for f in ("N1", "N2", "EGT", "FF") for k in (1, 2, 3, 4))


def gate0_standin(rec: FlightRecord, dtype: str) -> tuple[dict[str, tuple[np.ndarray, float]], int, int]:
    """A recorded-file stand-in for G0 built from a control flight: the 16 engine words stored with `dtype`,
    an 8-Hz VRTG on an affine float32 lattice, record frames (n / 4) and record seconds (n / 4).

    Returns (channels in round-1 `config.GROUP` order, record_frames, record_s)."""
    bits = _Bits("g0file", rec.flight_id, dtype)
    ch: dict[str, tuple[np.ndarray, float]] = {}
    for name in _STANDIN_ORDER:
        f, k = name.rsplit("_", 1)
        ch[name] = (np.asarray(rec.outputs[f][int(k) - 1]).astype(dtype), 4.0)
    code = np.array([1 + int(u * 4000) for u in bits.uniform(2 * rec.n)], float)
    a, b = STANDIN_AFFINE["VRTG"]
    ch["VRTG"] = ((code.astype(np.float32) * np.float32(a) + np.float32(b)).astype(np.float32), 8.0)
    return ch, rec.n // 4, len(rec.phase[::4])


def g0_control_matrices(rows: int = 40) -> dict[str, np.ndarray]:
    """Pipeline-only metadata matrices for G0 controls: `null_A`/`null_B` drawn from one distribution,
    `sep_A`/`sep_B` separable by the dtype column. Names in `names`."""
    u = np.array(_Bits("g0matrix").uniform(4 * rows * 3), float).reshape(4, rows, 3)

    def mk(v: np.ndarray, dtype_code: float) -> np.ndarray:
        return np.column_stack(
            [
                1000 + np.floor(200 * v[:, 0]),
                4000 + np.floor(800 * v[:, 0]),
                16000 + np.floor(3200 * v[:, 1]),
                np.full(rows, dtype_code),
                0.9 + 0.1 * v[:, 2],
            ]
        )

    return {
        "names": np.array(["record_frames", "record_s", "N1_1_n", "N1_1_dtype", "EGT_1_f32repr"]),
        "null_A": mk(u[0], 1.0),
        "null_B": mk(u[1], 1.0),
        "sep_A": mk(u[2], 1.0),
        "sep_B": mk(u[3], 0.0),
    }
