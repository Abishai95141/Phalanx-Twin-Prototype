"""DASHlink MAT -> recorded proxy-mode **inputs** (W2.4a drivers; architecture §14.3).

Only inputs are read for driving synthetic runs: per-engine PLA, pressure altitude, Mach, TAT, the ACMS flight
phase, weight on wheels, the autothrottle state (ATEN engage word, N1C command) and the
bleed/air-conditioning/anti-ice discretes (BLV, PACK, EAI, WAI_1/TAI; W2.4a-2, ``proxy.bleed``). Engine
outputs are never used to drive or tune anything here. Alignment follows the round-2 / M20 adapter rules
(``phalanx.validation.dashlink.load_record``): 4-Hz grid of the engine words, TAT (1 Hz) linearly
interpolated, PH/WOW/ATEN (1 Hz) held, the in-flight MACH = 0 sentinel interpolated.

Data files are untrusted: parsed with ``scipy.io.loadmat`` through the M20 adapter, never executed; paths are
arguments. Every path passes the A3 guard (:mod:`phalanx.proxy.guard`) before it is opened.
"""

from __future__ import annotations

import csv
import os
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from phalanx.scenario.replay import ReplayInputs
from phalanx.validation.dashlink import RATE, _clean_mach, load_mat

from .guard import check_path

FT = 0.3048
DEG = np.pi / 180.0
#: N1C values above this are invalid (all-ones words, 127.97 %: empirical_dashlink_texture.md Q2) and are held
N1C_VALID_MAX = 110.0


@dataclass(frozen=True)
class ProxyFlightInputs:
    """Recorded inputs of one DASHlink flight on the 4-Hz engine-word grid (n samples)."""

    flight_id: str
    rate_hz: float
    pla_deg: np.ndarray  # (4, n) power-lever angle per engine position
    alt_ft: np.ndarray  # (n,) pressure altitude
    mach: np.ndarray  # (n,)
    tat_c: np.ndarray  # (n,) total air temperature
    phase: np.ndarray  # (n,) DASHlink PH code
    wow: np.ndarray  # (n,) weight on wheels (as recorded)
    at_engage: np.ndarray  # (n,) 0/1 ATEN
    n1_cmd_pct: np.ndarray  # (n,) N1C, invalid words held at the last valid value
    #: bleed/air-conditioning/anti-ice discretes (n,) held to 4 Hz (W2.4a-2; ``proxy.bleed``); None = all off
    blv: np.ndarray | None = None  # BLV bleed-air valves (bit k = engine k + 1)
    pack: np.ndarray | None = None  # PACK air-conditioning packs (one bit per pack)
    eai: np.ndarray | None = None  # EAI engine anti-ice (bit k = engine k + 1)
    wai: np.ndarray | None = None  # 1 when the wing (WAI_1) or tail (TAI) anti-ice is on

    DISCRETES = ("blv", "pack", "eai", "wai")

    @property
    def n(self) -> int:
        return int(self.alt_ft.size)

    @property
    def n_engines(self) -> int:
        return int(self.pla_deg.shape[0])

    def window(self, a: int, b: int) -> ProxyFlightInputs:
        """Samples [a, b) of every series (a new object)."""
        return ProxyFlightInputs(
            self.flight_id,
            self.rate_hz,
            self.pla_deg[:, a:b].copy(),
            *(np.asarray(getattr(self, k))[a:b].copy() for k in
              ("alt_ft", "mach", "tat_c", "phase", "wow", "at_engage", "n1_cmd_pct")),
            *(None if getattr(self, k) is None else np.asarray(getattr(self, k))[a:b].copy()
              for k in self.DISCRETES),
        )  # fmt: skip

    def discrete(self, name: str) -> np.ndarray:
        """One bleed/anti-ice discrete as an int array (zeros when not recorded)."""
        x = getattr(self, name)
        return np.zeros(self.n, dtype=np.int64) if x is None else np.asarray(x, dtype=np.int64)

    def bleed(self, p) -> np.ndarray:
        """Customer bleed per engine [kg/s], (n_engines, n), by ``proxy.bleed.engine_bleed``."""
        from .bleed import engine_bleed

        return engine_bleed(
            *(self.discrete(k) for k in self.DISCRETES), p, n_engines=self.n_engines, ground=self.phase == 2
        )

    def replay_inputs(self, *, t0_ns: int = 0, epoch_utc_ns: int = 0) -> ReplayInputs:
        """The M02/M03/M04 replay record (SI): PLA rad, pressure altitude m, TAT K, A/T state and N1 command
        (fraction of 100 % N1, the same for every engine: no inner/outer split observed, Q5)."""
        e = self.pla_deg.shape[0]
        return ReplayInputs(
            t0_ns=int(t0_ns),
            rate_hz=float(self.rate_hz),
            epoch_utc_ns=int(epoch_utc_ns),
            pla_rad=self.pla_deg * DEG,
            phase=self.phase.astype(np.int64),
            pressure_alt_m=self.alt_ft * FT,
            mach=self.mach.astype(np.float64),
            tat_k=self.tat_c + 273.15,
            at_engage=self.at_engage.astype(np.int64),
            at_n1_cmd=np.tile(self.n1_cmd_pct / 100.0, (e, 1)),
        )


def _held(x: np.ndarray, rate: float, n: int) -> np.ndarray:
    t4 = np.arange(n) / RATE
    return x[np.minimum((t4 * rate).astype(int), x.size - 1)]


def _hold_invalid(x: np.ndarray, vmax: float) -> np.ndarray:
    """Replace invalid (all-ones) words by the last valid value (the first valid value before any)."""
    x = np.asarray(x, float).copy()
    valid = x <= vmax
    if not valid.any():
        return np.zeros_like(x)
    idx = np.where(valid, np.arange(x.size), -1)
    np.maximum.accumulate(idx, out=idx)
    idx[idx < 0] = int(np.flatnonzero(valid)[0])
    return x[idx]


def load_inputs(path: str | os.PathLike[str]) -> ProxyFlightInputs:
    """Recorded inputs of one DASHlink MAT file (A3-guarded; see the module docstring for the rules)."""
    p = check_path(path)
    F = load_mat(p)
    n = min(F[f"N1_{k}"].x.size for k in (1, 2, 3, 4))
    n = min(n, F["PLA_1"].x.size, F["ALT"].x.size, F["MACH"].x.size)
    t4 = np.arange(n) / RATE
    tat1 = F["TAT"].x.astype(float)
    tat = np.interp(t4, np.arange(tat1.size) / F["TAT"].rate, tat1)
    n1c = F["N1C"].x.astype(float)
    if F["N1C"].rate != RATE:
        n1c = _held(n1c, F["N1C"].rate, n)
    return ProxyFlightInputs(
        flight_id=p.name.replace(".mat", ""),
        rate_hz=RATE,
        pla_deg=np.vstack([F[f"PLA_{k}"].x[:n].astype(float) for k in (1, 2, 3, 4)]),
        alt_ft=F["ALT"].x[:n].astype(float),
        mach=_clean_mach(F["MACH"].x[:n]),
        tat_c=tat,
        phase=_held(F["PH"].x.astype(np.int64), F["PH"].rate, n),
        wow=_held(F["WOW"].x.astype(np.int64), F["WOW"].rate, n),
        at_engage=_held(F["ATEN"].x.astype(np.int64), F["ATEN"].rate, n),
        n1_cmd_pct=_hold_invalid(n1c[:n], N1C_VALID_MAX),
        blv=_held(F["BLV"].x.astype(np.int64), F["BLV"].rate, n),
        pack=_held(F["PACK"].x.astype(np.int64), F["PACK"].rate, n),
        eai=_held(F["EAI"].x.astype(np.int64), F["EAI"].rate, n),
        wai=(
            (_held(F["WAI_1"].x.astype(np.int64), F["WAI_1"].rate, n) > 0)
            | (_held(F["TAI"].x.astype(np.int64), F["TAI"].rate, n) > 0)
        ).astype(np.int64),
    )


def split_files(splits_csv: str | os.PathLike[str], subset: str = "687-CAL") -> tuple[str, ...]:
    """Sorted MAT file names of one round-1 split (``analysis/settling_experiment/results/splits.csv``)."""
    with open(splits_csv, newline="") as fh:
        return tuple(sorted(r["file"] for r in csv.DictReader(fh) if r["set"] == subset))


def airborne_window(
    inp: ProxyFlightInputs, *, phases=(3, 4, 5, 6), margin_s: float = 60.0
) -> tuple[int, int]:
    """[a, b) sample window from ``margin_s`` before the first to ``margin_s`` after the last sample whose PH
    is a flight phase (takeoff..approach): the inputs-only definition of the simulated segment (engines
    running and trimmed at its start; round-2's running-state rule was also PH-based, DEVIATIONS.md B3)."""
    on = np.flatnonzero(np.isin(inp.phase, phases))
    if on.size == 0:
        raise ValueError(f"{inp.flight_id}: no airborne phase")
    m = round(margin_s * inp.rate_hz)
    return max(0, int(on[0]) - m), min(inp.n, int(on[-1]) + 1 + m)


#: lever angle [deg] below which an engine's fuel is shut off (the M08 proxy ``pla_cutoff``); the DASHlink
#: lever reads about 0 deg with the engine shut down and 23-28 deg at idle
PLA_CUTOFF_DEG = 5.0
#: time allowed from the last engine's lever leaving cutoff to a stabilised ground idle [ASSUMPTION
#: A-W2.4a-16: airliner ground starts take 30-60 s to idle; the margin is generous so that the window starts
#: on running engines]
START_MARGIN_S = 120.0


def running_window(
    inp: ProxyFlightInputs, *, start_margin_s: float = START_MARGIN_S, cutoff_deg: float = PLA_CUTOFF_DEG
) -> tuple[int, int]:
    """[a, b) the whole-flight segment with every engine running, from the levers and PH only (inputs; no
    engine output is read).

    ``a`` is ``start_margin_s`` after the last lever leaves cutoff before the first flight phase; ``b`` is the
    first sample after the last flight phase at which any lever returns to cutoff (a shutdown in the taxi-in),
    or the end of the record. The taxi-out and taxi-in are kept, so the ground-idle samples that the battery's
    airborne rule (all N1 > 25 %) admits are reproduced (MF1-D DEVIATIONS D2)."""
    on = np.flatnonzero(np.isin(inp.phase, (3, 4, 5, 6)))
    if on.size == 0:
        raise ValueError(f"{inp.flight_id}: no flight phase")
    lever_on = inp.pla_deg > cutoff_deg  # (e, n)
    first_flight = int(on[0])
    starts = []
    for e in range(inp.n_engines):
        off = np.flatnonzero(~lever_on[e, :first_flight])
        starts.append(int(off[-1]) + 1 if off.size else 0)
    a = max(starts) + round(start_margin_s * inp.rate_hz)
    if a >= first_flight:
        raise ValueError(f"{inp.flight_id}: engines not all started {start_margin_s} s before the flight")
    last_flight = int(on[-1])
    shut = np.flatnonzero(~np.all(lever_on[:, last_flight:], axis=0))
    b = last_flight + int(shut[0]) if shut.size else inp.n
    return a, b


def synthetic_inputs(
    seconds: float = 30.0,
    *,
    alt_ft: float = 20000.0,
    mach: float = 0.6,
    tat_c: float = -10.0,
    pla_deg: float = 70.0,
    autothrottle: bool = True,
    n1_cmd_pct: float = 90.0,
    steps: tuple[tuple[float, float], ...] = ((10.0, 2.0), (20.0, -2.0)),
    flight_id: str = "synthetic",
) -> ProxyFlightInputs:
    """Deterministic synthetic recorded inputs (no data, no randomness) for tests, the A6 determinism check
    and the A2 identification self-test: a steady flight condition with step changes ``(t_s, delta)`` of the
    N1 command (A/T engaged) or of the lever (``autothrottle=False``, delta in deg). PH 5 (cruise)."""
    n = round(seconds * RATE)
    t = np.arange(n) / RATE
    cmd = np.full(n, float(n1_cmd_pct))
    pla = np.full(n, float(pla_deg))
    for ts, d in steps:
        if autothrottle:
            cmd[t >= ts] += d
        else:
            pla[t >= ts] += d
    return ProxyFlightInputs(
        flight_id=flight_id,
        rate_hz=RATE,
        pla_deg=np.tile(pla, (4, 1)),
        alt_ft=np.full(n, float(alt_ft)),
        mach=np.full(n, float(mach)),
        tat_c=np.full(n, float(tat_c)),
        phase=np.full(n, 5, dtype=np.int64),
        wow=np.ones(n, dtype=np.int64),
        at_engage=np.full(n, int(autothrottle), dtype=np.int64),
        n1_cmd_pct=cmd,
    )


def mat_path(mat_dir: str | os.PathLike[str], fname: str) -> Path:
    """Guarded path of one MAT file in a data directory."""
    return check_path(Path(mat_dir) / fname)


__all__ = [
    "N1C_VALID_MAX",
    "PLA_CUTOFF_DEG",
    "START_MARGIN_S",
    "ProxyFlightInputs",
    "airborne_window",
    "load_inputs",
    "mat_path",
    "running_window",
    "split_files",
    "synthetic_inputs",
]
