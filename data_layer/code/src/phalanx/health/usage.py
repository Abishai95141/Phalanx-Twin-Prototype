"""Usage drivers of M10 and the F404 life-usage-index (LUI) counting logic shared with M14.

Two consumers use one implementation, so the definitions cannot drift apart:

- **M10 (truth):** a sortie's usage drivers (cycles, time at temperature, starts, landings, g, dust and salt)
  are computed from *truth* signals in telemetry mode (:func:`usage_from_truth`) or supplied by the usage-mode
  surrogate (M02/W2.1) as a :class:`SortieUsage` event payload.
- **M14 (observation):** the ECMS counts the same LUIs from *measured* channels (CIR, with noise and
  quantisation), so noise can inflate counts exactly as on the CF-18 (8× partial N2 counts on one engine,
  Muir et al. AGARD-CP-448 p. 7-3 [DIRECT]); the hysteresis dead-band suppresses it when it is ≥ 2× the noise.

LUI definitions (8 GE LUIs, Hess AGARD-CP-448 pp. 2-5/2-6 [DIRECT: definitions]; gates and weights are not
public, so every gate is [ASSUMPTION] following ``f404_in20_engine_model.md`` Q9 "Recommended Phalanx LUI
implementation"; values live in ``configs/tejas/params/M14.yaml`` set ``lui``):

1. EOT: time with N2 ≥ ground-idle gate.
2. TAMP: time with PLA ≥ the IRP detent.
3. Type I: first off → intermediate (N2 ≥ IRP gate) → idle (N2 < lower gate) excursion of an engine run.
4. Type III: later idle → intermediate → idle excursions of the same run (hysteresis between the gates).
5. EFTC: rainflow (ASTM E1049 3-point) on T5 turning points with a dead-band; Σ (ΔT / ΔT_full)^b.
6. SRC: Σ dt · 2^((T5 − T_ref) / ΔT_2) in hours (Larson–Miller sensitivity, C ≈ 20 [TRANSFER]).
7. Full PS3 cycle: excursion with peak ≥ 95 % of PS3_max, closed below 50 %.
8. Partial PS3 cycle: excursion with peak in [85 %, 95 %) of PS3_max, closed below 50 %.

Plus Type IV (cruise → IRP → cruise; needed for the USAF TAC = Type I + Type III/4 + Type IV/40,
RTO-TR-028 / MIL-HDBK-1783B [TRANSFER]) and AB lights.

The counter is a pure streaming kernel over explicit state (``@njit`` + the same source as the NumPy
reference), so a flight processed in one block or in chunks gives identical counts (tested).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, fields

import numpy as np
from numba import njit

__all__ = [
    "LUI_FLOATS",
    "LUI_INTS",
    "NZ_LEVELS_DEFAULT",
    "SUMMARY_KEYS",
    "LuiGates",
    "SortieUsage",
    "lui_finalize",
    "lui_init",
    "lui_kernel",
    "lui_kernel_reference",
    "lui_readout",
    "nz_counter_kernel",
    "summary_payload",
    "tac",
    "usage_from_summary",
    "usage_from_truth",
]

# ------------------------------------------------------------------------------------------ sortie usage


@dataclass(frozen=True)
class SortieUsage:
    """Usage drivers of one sortie (payload of the ``health.sortie`` event). SI time in seconds.

    Per-engine quantities are tuples of length n_engines. Environment indices are dimensionless with 1.0 =
    nominal (dust and salt exposure of Indian desert and coastal bases, report §9 [ASSUMPTION scale]).
    """

    sortie_id: str
    flight_time_s: float
    eot_s: tuple[float, ...]
    tamp_s: tuple[float, ...]
    type1: tuple[float, ...]
    type3: tuple[float, ...]
    type4: tuple[float, ...]
    eftc: tuple[float, ...]
    src_h: tuple[float, ...]
    ps3_full: tuple[float, ...]
    ps3_partial: tuple[float, ...]
    ab_lights: tuple[float, ...]
    starts: tuple[float, ...]
    landings: float = 1.0
    gear_cycles: float = 1.0
    brake_energy_j: tuple[float, float] = (0.0, 0.0)
    nz_counts: tuple[float, ...] = (0.0,) * 8
    chute_streamings: float = 0.0
    jfs_starts: float = 1.0
    cold_soak: float = 0.0  # 1.0 when the aircraft was cold-soaked before the sortie
    dust: float = 1.0
    salt: float = 1.0
    humidity: float = 1.0
    thermal_cycle_k: float = 40.0  # avionics bay temperature swing of the sortie [K]
    #: AD-48.6 (telemetry mode): M09's in-sortie physical wear accrual of the two main brakes / tyres
    #: (``Utilities.sortie_wear``); empty = usage mode, M10's per-landing surrogate applies
    brake_wear_accrued: tuple[float, ...] = ()
    tyre_wear_accrued: tuple[float, ...] = ()
    extra: Mapping[str, float] = field(default_factory=dict)

    @property
    def n_engines(self) -> int:
        return len(self.eot_s)

    def __post_init__(self) -> None:
        n = len(self.eot_s)
        for f in fields(self):
            v = getattr(self, f.name)
            if f.name in _PER_ENGINE and len(v) != n:
                raise ValueError(f"{f.name}: expected {n} engines, got {len(v)}")
            if isinstance(v, float | int) and not isinstance(v, bool) and v < 0:
                raise ValueError(f"{f.name} must be >= 0")
        if self.flight_time_s < 0:
            raise ValueError("flight_time_s must be >= 0")
        for name in ("brake_wear_accrued", "tyre_wear_accrued"):
            v = getattr(self, name)
            if len(v) not in (0, 2) or any(x < 0 for x in v):
                raise ValueError(f"{name}: two non-negative main-wheel values (left, right) or none")

    def tac(self) -> tuple[float, ...]:
        """USAF TAC per engine: Type I + Type III/4 + Type IV/40 (RTO-TR-028 App. 1 [TRANSFER])."""
        return tuple(tac(a, b, c) for a, b, c in zip(self.type1, self.type3, self.type4, strict=True))

    def to_payload(self) -> dict[str, object]:
        p: dict[str, object] = {}
        for f in fields(self):
            v = getattr(self, f.name)
            if f.name == "extra":
                for k in sorted(v):
                    p[f"x_{k}"] = float(v[k])
            elif f.name == "sortie_id":
                p[f.name] = str(v)
            elif isinstance(v, tuple):
                p[f.name] = np.asarray(v, dtype=np.float64)
            else:
                p[f.name] = float(v)
        return p

    @classmethod
    def from_payload(cls, payload: Mapping[str, np.ndarray]) -> SortieUsage:
        kw: dict[str, object] = {}
        extra: dict[str, float] = {}
        for k, v in payload.items():
            if k.startswith("x_"):
                extra[k[2:]] = float(v)
                continue
            if k == "sortie_id":
                kw[k] = str(np.asarray(v).item())
            elif np.asarray(v).ndim == 1:
                kw[k] = tuple(float(x) for x in np.asarray(v))
            else:
                kw[k] = float(v)
        kw["extra"] = extra
        return cls(**kw)  # type: ignore[arg-type]


_PER_ENGINE = frozenset(
    {
        "eot_s",
        "tamp_s",
        "type1",
        "type3",
        "type4",
        "eftc",
        "src_h",
        "ps3_full",
        "ps3_partial",
        "ab_lights",
        "starts",
    }
)


def tac(type1: float, type3: float, type4: float) -> float:
    """Total accumulated cycles TAC = Type I + Type III/4 + Type IV/40 (MIL-HDBK-1783B [TRANSFER])."""
    return type1 + type3 / 4.0 + type4 / 40.0


# ------------------------------------------------------------------------------------------ LUI kernel
#: float state of the LUI counter
LUI_FLOATS: tuple[str, ...] = (
    "eot_s",
    "tamp_s",
    "type1",
    "type3",
    "type4",
    "eftc",
    "src_h",
    "ps3_full",
    "ps3_partial",
    "t5_ext",  # current T5 extremum candidate of the turning-point detector
)
EOT_S, TAMP_S, TYPE1, TYPE3, TYPE4, EFTC, SRC_H, PS3_FULL, PS3_PART, T5_EXT = range(10)
#: int state of the LUI counter
LUI_INTS: tuple[str, ...] = (
    "last_t",  # time of the previous sample [ns]
    "have_last",
    "running",  # engine run in progress (N2 above the run gate)
    "first_done",  # Type I counted in this run
    "had_peak",  # reached the IRP gate since the last time below the lower gate
    "cruise_dip",  # dropped below the cruise gate (not the lower gate) after a peak
    "ps3_class",  # 0 none, 1 partial (>= 85 %), 2 full (>= 95 %) since the last close below 50 %
    "t5_dir",  # turning-point detector direction: 0 unknown, +1 rising, -1 falling
    "t5_init",
    "rf_n",  # number of turning points on the rainflow stack
    "gap",  # data gap seen (invalid input or dt > dt_gap)
    "n_samples",
)
(
    LAST_T,
    HAVE_LAST,
    RUNNING,
    FIRST_DONE,
    HAD_PEAK,
    CRUISE_DIP,
    PS3_CLASS,
    T5_DIR,
    T5_INIT,
    RF_N,
    GAP,
    N_SAMP,
) = range(12)
RF_CAP = 256  # rainflow residue capacity (turning points); overflow counts the oldest range as a half cycle


@dataclass(frozen=True)
class LuiGates:
    """LUI gates in the units of the signals the kernel is fed (EU for CIR, SI for truth).

    Order of the flat vector: n2_run, n2_off, n2_idle, n2_low, n2_cruise, n2_irp, pla_irp, ps3_max, t5_ref,
    t5_doubling, t5_full_swing, eftc_exponent, t5_deadband, dt_max_s, dt_gap_s.
    """

    n2_run: float
    n2_off: float
    n2_idle: float
    n2_low: float
    n2_cruise: float
    n2_irp: float
    pla_irp: float
    ps3_max: float
    t5_ref: float
    t5_doubling: float
    t5_full_swing: float
    eftc_exponent: float
    t5_deadband: float
    dt_max_s: float
    dt_gap_s: float

    def __post_init__(self) -> None:
        if not (self.n2_off < self.n2_run and self.n2_low < self.n2_cruise < self.n2_irp):
            raise ValueError("N2 gates must satisfy off < run and low < cruise < irp")
        if self.t5_deadband <= 0 or self.t5_full_swing <= 0 or self.t5_doubling <= 0:
            raise ValueError("T5 dead-band, full swing and doubling must be > 0")

    def vector(self) -> np.ndarray:
        v = np.array([getattr(self, f.name) for f in fields(self)], dtype=np.float64)
        v.flags.writeable = False
        return v


(
    G_RUN,
    G_OFF,
    G_IDLE,
    G_LOW,
    G_CRUISE,
    G_IRP,
    G_PLA,
    G_PS3MAX,
    G_TREF,
    G_TDBL,
    G_TFULL,
    G_B,
    G_TDB,
    G_DTMAX,
    G_DTGAP,
) = range(15)


def lui_init() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Fresh LUI state: (floats, ints, rainflow stack)."""
    return (
        np.zeros(len(LUI_FLOATS), np.float64),
        np.zeros(len(LUI_INTS), np.int64),
        np.zeros(RF_CAP, np.float64),
    )


@njit(cache=True, fastmath=False, error_model="numpy", nogil=True)
def _rf_push(stack, n, x, g, f):
    """Push turning point x and extract closed rainflow cycles (3-point method); returns new n."""
    if n == stack.shape[0]:  # overflow: count the oldest range as a half cycle and drop the oldest point
        r = abs(stack[1] - stack[0])
        f[EFTC] += 0.5 * (r / g[G_TFULL]) ** g[G_B]
        for j in range(n - 1):
            stack[j] = stack[j + 1]
        n -= 1
    stack[n] = x
    n += 1
    while n >= 3:
        xr = abs(stack[n - 1] - stack[n - 2])
        yr = abs(stack[n - 2] - stack[n - 3])
        if xr < yr:
            break
        if n == 3:  # Y contains the starting point: half cycle, discard the first point
            f[EFTC] += 0.5 * (yr / g[G_TFULL]) ** g[G_B]
            stack[0] = stack[1]
            stack[1] = stack[2]
            n = 2
        else:  # full cycle: discard the two points of Y
            f[EFTC] += (yr / g[G_TFULL]) ** g[G_B]
            stack[n - 3] = stack[n - 1]
            n -= 2
    return n


@njit(cache=True, fastmath=False, error_model="numpy", nogil=True)
def _lui_kernel(f, i, stack, g, t_ns, n2, ps3, t5, pla, valid):
    """Advance the LUI counter over samples (aligned, time-ordered). Pure: returns new (f, i, stack)."""
    f = f.copy()
    i = i.copy()
    stack = stack.copy()
    for k in range(t_ns.shape[0]):
        i[N_SAMP] += 1
        if not valid[k]:
            i[GAP] = 1
            continue
        dt = 0.0
        if i[HAVE_LAST] == 1:
            dt = (t_ns[k] - i[LAST_T]) * 1e-9
            if dt > g[G_DTGAP]:
                i[GAP] = 1
            if dt > g[G_DTMAX]:
                dt = g[G_DTMAX]
            if dt < 0.0:
                dt = 0.0
        i[LAST_T] = t_ns[k]
        i[HAVE_LAST] = 1
        x2 = n2[k]
        # EOT and TAMP integrate the interval ending at this sample (left value held = this sample's level)
        if x2 >= g[G_IDLE]:
            f[EOT_S] += dt
        if pla[k] >= g[G_PLA]:
            f[TAMP_S] += dt
        f[SRC_H] += dt / 3600.0 * 2.0 ** ((t5[k] - g[G_TREF]) / g[G_TDBL])
        # engine run gating
        if i[RUNNING] == 0:
            if x2 >= g[G_RUN]:
                i[RUNNING] = 1
                i[FIRST_DONE] = 0
                i[HAD_PEAK] = 0
                i[CRUISE_DIP] = 0
        else:
            if x2 < g[G_OFF]:
                if i[HAD_PEAK] == 1:  # spool-down from a peak closes the cycle through idle
                    if i[FIRST_DONE] == 0:
                        f[TYPE1] += 1.0
                    else:
                        f[TYPE3] += 1.0
                i[RUNNING] = 0
                i[HAD_PEAK] = 0
                i[CRUISE_DIP] = 0
                i[FIRST_DONE] = 0
        if i[RUNNING] == 1:
            if x2 >= g[G_IRP]:
                if i[CRUISE_DIP] == 1:
                    f[TYPE4] += 1.0
                    i[CRUISE_DIP] = 0
                i[HAD_PEAK] = 1
            elif x2 < g[G_LOW]:
                if i[HAD_PEAK] == 1:
                    if i[FIRST_DONE] == 0:
                        f[TYPE1] += 1.0
                        i[FIRST_DONE] = 1
                    else:
                        f[TYPE3] += 1.0
                i[HAD_PEAK] = 0
                i[CRUISE_DIP] = 0
            elif x2 < g[G_CRUISE]:
                if i[HAD_PEAK] == 1:
                    i[CRUISE_DIP] = 1
        # PS3 cycles (peak class closed below 50 % of PS3_max)
        p = ps3[k] / g[G_PS3MAX]
        if p >= 0.95:
            i[PS3_CLASS] = 2
        elif p >= 0.85 and i[PS3_CLASS] < 1:
            i[PS3_CLASS] = 1
        elif p < 0.50:
            if i[PS3_CLASS] == 2:
                f[PS3_FULL] += 1.0
            elif i[PS3_CLASS] == 1:
                f[PS3_PART] += 1.0
            i[PS3_CLASS] = 0
        # T5 turning points with a dead-band, then rainflow
        x5 = t5[k]
        if i[T5_INIT] == 0:
            f[T5_EXT] = x5
            i[T5_INIT] = 1
            i[T5_DIR] = 0
        elif i[T5_DIR] == 0:
            if x5 > f[T5_EXT] + g[G_TDB]:
                i[RF_N] = _rf_push(stack, i[RF_N], f[T5_EXT], g, f)
                i[T5_DIR] = 1
                f[T5_EXT] = x5
            elif x5 < f[T5_EXT] - g[G_TDB]:
                i[RF_N] = _rf_push(stack, i[RF_N], f[T5_EXT], g, f)
                i[T5_DIR] = -1
                f[T5_EXT] = x5
        elif i[T5_DIR] == 1:
            if x5 > f[T5_EXT]:
                f[T5_EXT] = x5
            elif x5 < f[T5_EXT] - g[G_TDB]:
                i[RF_N] = _rf_push(stack, i[RF_N], f[T5_EXT], g, f)
                i[T5_DIR] = -1
                f[T5_EXT] = x5
        else:
            if x5 < f[T5_EXT]:
                f[T5_EXT] = x5
            elif x5 > f[T5_EXT] + g[G_TDB]:
                i[RF_N] = _rf_push(stack, i[RF_N], f[T5_EXT], g, f)
                i[T5_DIR] = 1
                f[T5_EXT] = x5
    return f, i, stack


def lui_kernel(f, i, stack, gates: np.ndarray, t_ns, n2, ps3, t5, pla, valid):
    """Compiled LUI counter (see module docstring); inputs are 1-D aligned arrays."""
    return _lui_kernel(
        f,
        i,
        stack,
        gates,
        np.ascontiguousarray(t_ns, np.int64),
        np.ascontiguousarray(n2, np.float64),
        np.ascontiguousarray(ps3, np.float64),
        np.ascontiguousarray(t5, np.float64),
        np.ascontiguousarray(pla, np.float64),
        np.ascontiguousarray(valid, np.bool_),
    )


def lui_kernel_reference(f, i, stack, gates, t_ns, n2, ps3, t5, pla, valid):
    """The NumPy reference: the same source uncompiled (bitwise equal to :func:`lui_kernel`, tested)."""
    return _lui_kernel.py_func(
        f,
        i,
        stack,
        gates,
        np.ascontiguousarray(t_ns, np.int64),
        np.ascontiguousarray(n2, np.float64),
        np.ascontiguousarray(ps3, np.float64),
        np.ascontiguousarray(t5, np.float64),
        np.ascontiguousarray(pla, np.float64),
        np.ascontiguousarray(valid, np.bool_),
    )


def lui_finalize(f, i, stack, gates: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """End of flight: push the last T5 extremum and count the rainflow residue as half cycles (ASTM E1049).

    Pure; the counter can continue afterwards (a new flight starts from an empty residue).
    """
    f = f.copy()
    i = i.copy()
    stack = stack.copy()
    if i[T5_INIT] == 1:
        n = int(i[RF_N])
        if n < RF_CAP:  # the last extremum candidate is the final turning point
            stack[n] = f[T5_EXT]
            n += 1
        for j in range(n - 1):
            r = abs(stack[j + 1] - stack[j])
            f[EFTC] += 0.5 * (r / gates[G_TFULL]) ** gates[G_B]
    i[RF_N] = 0
    i[T5_INIT] = 0
    i[T5_DIR] = 0
    stack[:] = 0.0
    return f, i, stack


def lui_readout(f: np.ndarray) -> dict[str, float]:
    """The counters as a name -> value mapping (EOT and TAMP in seconds, SRC in hours)."""
    return {n: float(f[j]) for j, n in enumerate(LUI_FLOATS) if n != "t5_ext"}


# ------------------------------------------------------------------------------------------ Nz counters
#: 8 level-crossing g-levels (fatigue-meter practice, JOAST 55(1) 2003 [TRANSFER: count of levels]; the levels
#: themselves are not public for Tejas [ASSUMPTION]; the parameter file holds the values used)
NZ_LEVELS_DEFAULT = (-1.0, 0.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0)


@njit(cache=True, fastmath=False, error_model="numpy", nogil=True)
def nz_counter_kernel(counts, armed, levels, rearm, nz):
    """Level-crossing counts: a level above ``rearm`` counts when Nz ≥ level while armed and re-arms below
    ``rearm``; a level below counts when Nz ≤ level and re-arms above. Pure: returns new (counts, armed)."""
    counts = counts.copy()
    armed = armed.copy()
    for k in range(nz.shape[0]):
        x = nz[k]
        for j in range(levels.shape[0]):
            lv = levels[j]
            if lv > rearm:
                if armed[j] == 1 and x >= lv:
                    counts[j] += 1.0
                    armed[j] = 0
                elif armed[j] == 0 and x < rearm:
                    armed[j] = 1
            else:
                if armed[j] == 1 and x <= lv:
                    counts[j] += 1.0
                    armed[j] = 0
                elif armed[j] == 0 and x > rearm:
                    armed[j] = 1
    return counts, armed


# ------------------------------------------------------------------------------------------ truth usage
def usage_from_truth(
    sortie_id: str,
    t_ns: np.ndarray,
    n2: np.ndarray,
    ps3: np.ndarray,
    t5: np.ndarray,
    pla: np.ndarray,
    gates: LuiGates,
    *,
    nz: np.ndarray | None = None,
    nz_levels: tuple[float, ...] = NZ_LEVELS_DEFAULT,
    nz_rearm: float = 1.0,
    flight_time_s: float | None = None,
    ab_lights: tuple[float, ...] | None = None,
    starts: tuple[float, ...] | None = None,
    **env: float,
) -> SortieUsage:
    """A sortie's usage drivers from truth time series (telemetry mode). Arrays are (n_engines, n) for engine
    signals and (n,) for ``t_ns`` / ``nz``; ``gates`` must be in the units of the arrays."""
    n2 = np.atleast_2d(n2)
    ps3, t5, pla = np.atleast_2d(ps3), np.atleast_2d(t5), np.atleast_2d(pla)
    ne = n2.shape[0]
    g = gates.vector()
    per: dict[str, list[float]] = {
        k: [] for k in ("eot_s", "tamp_s", "type1", "type3", "type4", "eftc", "src_h")
    }
    per |= {"ps3_full": [], "ps3_partial": []}
    valid = np.ones(t_ns.shape[0], np.bool_)
    for e in range(ne):
        f, i, st = lui_init()
        f, i, st = lui_kernel(f, i, st, g, t_ns, n2[e], ps3[e], t5[e], pla[e], valid)
        f, i, st = lui_finalize(f, i, st, g)
        r = lui_readout(f)
        for k in per:
            per[k].append(r[k])
    counts = np.zeros(len(nz_levels))
    if nz is not None:
        counts, _ = nz_counter_kernel(
            counts, np.ones(len(nz_levels), np.int64), np.asarray(nz_levels, np.float64), float(nz_rearm), nz
        )
    ft = float(flight_time_s) if flight_time_s is not None else float(t_ns[-1] - t_ns[0]) * 1e-9
    return SortieUsage(
        sortie_id=sortie_id,
        flight_time_s=ft,
        ab_lights=ab_lights or (0.0,) * ne,
        starts=starts or (1.0,) * ne,
        nz_counts=tuple(float(c) for c in counts),
        **{k: tuple(v) for k, v in per.items()},
        **env,
    )


# ------------------------------------------------------------------------------------------ sortie summary
#: catalogued payload keys of ``usage.sortie_summary`` (AD-44, M02 -> M10)
SUMMARY_KEYS: tuple[str, ...] = (
    "sortie_id",
    "tail_no",
    "flight_hours",
    "engine_cycles",
    "engine_starts",
    "landings",
    "time_at_temp_s",
    "max_nz",
    "ab_time_s",
    "dust_index",
    "salt_index",
)


def summary_payload(u: SortieUsage, tail_no: str, *, max_nz: float = 1.0) -> dict[str, object]:
    """A ``usage.sortie_summary`` doc for a sortie whose full usage is known (telemetry mode: the drivers from
    truth, :func:`usage_from_truth`). It carries the catalogued keys plus ``usage`` (the full
    :class:`SortieUsage`), which :func:`usage_from_summary` reads back exactly."""
    return {
        "sortie_id": u.sortie_id,
        "tail_no": tail_no,
        "flight_hours": u.flight_time_s / 3600.0,
        "engine_cycles": float(max(u.tac())) if u.type1 else 0.0,  # TAC (as M18 uses it)
        "engine_starts": float(max(u.starts)) if u.starts else 0.0,
        "landings": u.landings,
        "time_at_temp_s": float(max(u.tamp_s)) if u.tamp_s else 0.0,
        "max_nz": float(max_nz),
        "ab_time_s": 0.0,
        "dust_index": u.dust,
        "salt_index": u.salt,
        "usage": {k: (v.tolist() if isinstance(v, np.ndarray) else v) for k, v in u.to_payload().items()},
    }


def usage_from_summary(d: Mapping[str, object], params, n_engines: int) -> SortieUsage:
    """The :class:`SortieUsage` of a ``usage.sortie_summary`` doc (usage mode, A-W1.5-17).

    A doc carrying ``usage`` (telemetry mode) is read back exactly. Otherwise the aircraft-level summary is
    expanded per engine with design-usage rates [TRANSFER: MIL-HDBK-1783B / JSSG-2007A fighter design usage,
    research_notes flight_profiles_and_usage.md Q3]:

    - EOT = flight time × ``eot_per_fh``; Type I = ``engine_starts`` (one start-max-stop per start);
    - ``engine_cycles`` is read as the sortie's TAC (as M18 uses it, ~2.5 per hour): the TAC above Type I is
      split into Type III and IV in the design ratio, so TAC = I + III/4 + IV/40 holds; without it, Type III
      and IV follow the design rates per flight hour;
    - AB lights per afterburner second; TAMP = ``time_at_temp_s``; full PS3 cycles = Type I, partial = Type
      III;
    - EFTC = Type I + w3 Type III + w4 Type IV; SRC = TAMP hours + ``src_cold_factor`` × the other EOT hours;
    - brake energy = the reference stop energy per wheel per landing;
    - **PROXY (A-W1.5-18):** Nz level crossings from ``max_nz`` alone: one crossing of every positive counter
      level up to ``max_nz``, none of the negative ones (a lower bound of the real spectrum).
    """
    if "usage" in d:
        return SortieUsage.from_payload(dict(d["usage"]))  # type: ignore[call-overload]

    def num(k: str, default: float = 0.0) -> float:
        v = d.get(k, default)
        return float(default if v is None else v)  # type: ignore[arg-type]

    def prm(name: str) -> float:
        return float(params.value(name))

    fh = num("flight_hours")
    ft = fh * 3600.0
    eot = ft * prm("eot_per_fh")
    t1 = num("engine_starts")
    t3 = ft * prm("type3_per_fh")  # rates are SI (per second) after loading
    t4 = ft * prm("type4_per_fh")
    residual = num("engine_cycles") - t1
    if residual > 0.0:  # the reported TAC sets the sortie's cycle severity
        r = prm("type4_per_fh") / prm("type3_per_fh")
        t3 = residual / (0.25 + r / 40.0)
        t4 = r * t3
    tat = min(num("time_at_temp_s"), eot)
    src = tat / 3600.0 + prm("src_cold_factor") * max(0.0, eot - tat) / 3600.0
    e = int(n_engines)
    max_nz = num("max_nz", 1.0)
    nz = tuple(1.0 if (lv > 1.0 and max_nz >= lv) else 0.0 for lv in NZ_LEVELS_DEFAULT)
    stop = prm("brake_energy_ref") * num("landings")
    return SortieUsage(
        sortie_id=str(d["sortie_id"]),
        flight_time_s=ft,
        eot_s=(eot,) * e,
        tamp_s=(tat,) * e,
        type1=(t1,) * e,
        type3=(t3,) * e,
        type4=(t4,) * e,
        eftc=(t1 + prm("eftc_w_type3") * t3 + prm("eftc_w_type4") * t4,) * e,
        src_h=(src,) * e,
        ps3_full=(t1,) * e,
        ps3_partial=(t3,) * e,
        ab_lights=(num("ab_time_s") * prm("ab_lights_per_ab_s"),) * e,
        starts=(num("engine_starts"),) * e,
        landings=num("landings"),
        gear_cycles=num("landings"),
        brake_energy_j=(stop, stop),
        nz_counts=nz,
        chute_streamings=num("chute_streamed"),
        jfs_starts=num("engine_starts"),
        dust=num("dust_index", 1.0),
        salt=num("salt_index", 1.0),
    )
