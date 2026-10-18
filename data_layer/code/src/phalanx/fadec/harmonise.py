"""M08 schedules harmonised with the M07 engine model (W2.1b; W2.1 entry gate 2; AD-50, A-W1.3a-12).

The FADEC is designed for the nominal engine: its schedules and on-board model come from steady-state sweeps
of the **nominal M07 model** (no health deltas, no disturbances), never from the W1 TEST FIXTURE plant (AD-50:
fixture-matched tables are circular). This module derives them. The CSV files and the M08.yaml values it
produces are committed under ``configs/<platform>/params/M08/``, and a drift test
(``tests/integration/test_fadec_harmonise.py``) fails when they no longer equal what M07 gives, so any M07
recalibration (W2.3, W2.4a) forces a regeneration (``write_harmonised``).

Derivation (SLS ISA, Mach 0, dry air; every input is a tagged M08 or M07 parameter):

1. **Variable geometry** = M07's reference schedules (``steady.vg_reference``; A-W1.3a-12: the maps are on
   schedule only there). FVG(N1/sqrt(theta1)) is copied; CVG is re-based from M07's axis (fraction of the
   design corrected core speed ``n2c_des_rpm``) to M08's (N2/sqrt(theta25) as a fraction of 16,810 rpm).
2. **Nozzle floor scale** ``a8_scale``: the -400 PLA floor schedule (``a8_pla``, TRANSFER) is scaled so that,
   at the N1-limit onset PLA (``harm_n1_onset_pla``), it equals the SLS throat A8* at which M07 reaches the N1
   and T5 limits together. So NL and T5 reach their limits together "just prior to IRP" (CR-1998-208416
   §7.2), the IRP floor is below A8* and the T5 loop holds T5 at IRP ("A8 modulated to hold T5 at and above
   IRP", TM-104247), and the throttle map has no step: with a smaller floor at the onset T5 binds first on
   the floor and, a degree later, the T5 loop runs the nozzle open to the N1 limit (a step in N1). The
   flow-ratio scale it replaces (1.087) put the IRP floor above M07's T5-limited throat, so the T5 loop was
   never in control at IRP. The clamps ``a8_min``/``a8_max`` are M07's actuator stops (``a8_min_ratio``,
   ``a8_max_ratio`` of the MIL throat), so the FADEC can command every throat the engine has (the W1.3b defect
   "a8_min 0.154 m^2 above M07's MIL throat 0.138 m^2").
3. **Core-speed demand** ``n2c_pla`` (N2/sqrt(theta25) vs PLA): the W1.3b schedule shape (``n2c_pla_shape``,
   A-W1.3b-4) is mapped affinely onto M07's corrected-speed range, anchored at ground idle (PLA ``pla_gi`` ->
   the physical ground-idle N2 ``harm_idle_n2``) and at the N1-limit onset (PLA ``harm_n1_onset_pla`` -> the
   corrected core speed of the A8* point). On the W1.3b (fixture-matched) schedule M07 reached the N1 limit
   at about PLA 65-70, where the fast-band FF correlation sign inverts (E1 §8).
4. **Ratio-unit schedules** ``ru_ff`` (vs the demanded N2/sqrt(theta25)) and ``ru_ref`` (vs N2/sqrt(theta1)):
   Wf/PS3 of M07 along that operating line. Below ground idle, ``ru_ref`` continues on M07's steady line at
   the idle nozzle floor down to ``harm_line_min_n2c`` (W2.3a): there the steady Wf/PS3 of the engine *rises*
   as N2 falls (component efficiencies fall and the fixed extraction grows relative to the core flow), so a
   reference that falls below idle (the W1.3b shape) crosses the loaded requirement a few points below idle
   and a small sag rolls the engine back (W2.5 DEVIATIONS D3). Below ``harm_line_min_n2c`` (the start regime,
   where M08's start logic replaces the accel schedule, A-W1.3b-18) and above the SLS N1-limit onset the
   W1.3b reference shape (``ru_ref_shape``) is scaled to join the line at each end; the feed-forward is held
   flat outside the line.

5. **On-board model** ``obm_*`` (the FICA-style structure of A-W1.3b-7): N1c(N2c), PS3/P0(N2c), T25/T1(N1c)
   and T5/T1(N2c) along the same line (theta1 corrections).

**Design conditions (W2.3a).** The anchors of steps 2-3 (nozzle scale, ground-idle and N1-onset demand) are
taken on the bare engine at SLS ISA, as the test-cell evidence they rest on (KSAS/IERA idle, CR-1998-208416
"NL reaches its limit just prior to IRP" in an engine test). The fuel-control lines of steps 4-5 (reference,
accel/decel shape, feed-forward, on-board model) are derived for the **installed** nominal engine: SLS ISA
with the aircraft's nominal ground extraction (``harm_bleed`` customer bleed, ``harm_pto`` shaft power
off-take; M09's nominal ground values). A FADEC's accel/decel schedules are laid out against the steady
line of the installed engine (they must keep their margins with the customer extraction on); deriving them
from the no-load engine left only 3-20 % accel margin at ground idle once M09's loads (about 22 kW PTO,
0.5 kg/s bleed) and B7-level deterioration were present (W2.5 D3). At high power the extraction is about
1 % of the core flow, so the line there is essentially the bare engine's.

Columns are returned in the CSV units (deg, lb/h/psi, dimensionless); scalars in the M08.yaml units (in^2 for
``a8_min``/``a8_max``).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from phalanx.core.module import ParamSet

from .codes import L_N1
from .params import FadecConfig
from .trim import operating_point

IN2 = 0.0254 * 0.0254  # m^2 per in^2
LB = 0.45359237  # kg
PSI = 6894.757293168361  # Pa
RU_SI = LB / 3600.0 / PSI  # (kg/s)/Pa per (lb/h)/psi
T_STD = 288.15
P_STD = 101325.0
#: points of the operating-line sweep from ground idle to the N1-limit onset (deterministic grid)
N_LINE = 24
#: decimals written to the CSV files (the drift test compares at this resolution)
CSV_DECIMALS = 6


@dataclass(frozen=True)
class LinePoint:
    """One M07 steady state on the harmonised SLS operating line."""

    pla_deg: float
    n2c25: float  # N2/sqrt(theta25), fraction of 16,810 rpm
    n2c1: float  # N2/sqrt(theta1)
    n1c1: float  # N1/sqrt(theta1), fraction of 13,270 rpm
    n2: float  # physical fractions
    n1: float
    ru_pph_psi: float  # Wf/PS3, lb/h/psi
    ps3_p0: float
    t25_t1: float
    t5_t1: float
    t5_k: float
    a8_m2: float
    wf_kgs: float
    fn_n: float


@dataclass(frozen=True)
class Harmonised:
    """Derived M08 tables (CSV name -> (header, columns)) and scalars (M08.yaml name -> value, yaml units)."""

    tables: dict[str, tuple[tuple[str, ...], tuple[np.ndarray, ...]]]
    scalars: dict[str, float]
    line: tuple[LinePoint, ...]
    anchors: dict[str, float] = field(default_factory=dict)
    sub_idle: tuple[LinePoint, ...] = ()  # installed steady points below ground idle (ascending N2)


def _with(cfg: FadecConfig, tables: dict[str, np.ndarray], p: dict[str, float]) -> FadecConfig:
    """A copy of ``cfg`` with some tables (``layout.Tables`` field names) and kernel parameters replaced."""
    from dataclasses import replace

    from .layout import P_LAYOUT

    pv = cfg.p.copy()
    for k, x in p.items():
        pv[P_LAYOUT.index[k]] = float(x)
    pv.flags.writeable = False
    tb = cfg.tables._replace(**{k: np.ascontiguousarray(np.asarray(x, float)) for k, x in tables.items()})
    return replace(cfg, p=pv, tables=tb)


def _interp(x, xp, fp) -> float:
    return float(np.interp(float(x), np.asarray(xp, float), np.asarray(fp, float)))


def _point(res, pla_deg: float) -> LinePoint:
    from phalanx.engine.layout import AUX_NAMES, U_A8, U_WF, X_N1, X_N2

    a = {n: float(res.aux[j]) for j, n in enumerate(AUX_NAMES)}
    n1r = 13270.0 * 2.0 * np.pi / 60.0
    n2r = 16810.0 * 2.0 * np.pi / 60.0
    sth1 = float(np.sqrt(a["t2"] / T_STD))
    n2 = float(res.x[X_N2]) / n2r
    n1 = float(res.x[X_N1]) / n1r
    wf = float(res.u[U_WF])
    return LinePoint(
        pla_deg=float(pla_deg),
        n2c25=a["n2c"] / 16810.0,
        n2c1=n2 / sth1,
        n1c1=n1 / sth1,
        n2=n2,
        n1=n1,
        ru_pph_psi=wf / a["ps3"] / RU_SI,
        ps3_p0=a["ps3"] / P_STD,
        t25_t1=a["t25"] / a["t2"],
        t5_t1=a["t5"] / a["t2"],
        t5_k=a["t5"],
        a8_m2=float(res.u[U_A8]),
        wf_kgs=wf,
        fn_n=a["fn"],
    )


#: spacing (N2/sqrt(theta1), fraction of 16,810 rpm) of the sub-idle steady points of the reference line
SUB_IDLE_STEP = 0.01


def sub_idle_line(model: Any, cond: Any, a8: float, n2c_idle: float, n2c_min: float, x0) -> list[LinePoint]:
    """M07 equilibria below ground idle (ascending in N2/sqrt(theta1)): the steady fuel the installed engine
    needs to hold each core speed between ``n2c_min`` and the idle point ``n2c_idle`` (exclusive) on the idle
    nozzle floor ``a8``, VG on the reference schedule (= M08's harmonised VG). Points on a fixed grid of
    ``SUB_IDLE_STEP`` from ``n2c_min`` upwards, solved downwards from the idle state by continuation
    (deterministic). Empty when ``n2c_min`` is at or above idle.

    The sub-idle points lie in M07's map range for the core (HPC speed lines from 50 % of the design corrected
    speed) and on the fan-law extrapolation below the lowest fan speed line (PROXY A-W1.3a-3) for the fan."""
    from phalanx.engine.steady import trim

    t2 = float(cond.t_s)  # SLS static: T1 = T_s (M0)
    sth1 = float(np.sqrt(t2 / T_STD))
    n2r = 16810.0 * 2.0 * np.pi / 60.0
    k_hi = int(np.floor((n2c_idle - n2c_min) / SUB_IDLE_STEP - 1e-9))
    grid = [n2c_min + k * SUB_IDLE_STEP for k in range(k_hi + 1)]
    grid = [g for g in grid if g < n2c_idle - 0.25 * SUB_IDLE_STEP]
    out: list[LinePoint] = []
    x = x0
    for g in reversed(grid):
        r = trim(model, cond, ("n2", g * sth1 * n2r), a8=a8, x0=x)
        if not r.converged:
            raise RuntimeError(f"harmonise: M07 sub-idle point at N2c {g:.3f} did not converge")
        x = r.x
        out.append(_point(r, float("nan")))
    return out[::-1]


def governor_gain_schedule(x, ru, kp: float, margin: float) -> tuple[tuple[str, ...], tuple[np.ndarray, ...]]:
    """N2-governor gain multiplier vs N2/sqrt(theta1) from the installed steady line (W2.3a, A-W2.3-3).

    With ratio-unit fuelling (Wf = RU x PS3) the engine at a fixed RU is unstable wherever its steady Wf/PS3
    falls as N2 rises (near ground idle: component efficiencies fall and the fixed extraction grows as N2
    falls). The governor's proportional ratio-unit gain per unit N2 error, kp x RU_ref, must then exceed the
    slope -dRU/dN2c: the multiplier is max(1, margin x max(0, -dRU/dN2c) / (kp x RU)), with the slope from
    centred differences along the line (x ascending), so it is 1 wherever the line rises (AD-57's Kp). The
    ``margin`` (``gov_ks_margin``) is set on the M07+M08 loop by the GM > 6 dB / PM > 45 deg rule of
    C-MAPSS40k's scheduled setpoint loops, applied as a step overshoot below 23 % on the W2.5 idle load and
    deterioration step for every B7 case (``tests/integration/test_fadec_accel_margin.py``): on the W2.1b M07,
    margin 5 (x5.4 at ground idle) overshoots at most 15 %; 2.5 overshot up to 83 %, and without the schedule
    a 1 s idle kick at the integrated aircraft's loads did not decay."""
    x = np.asarray(x, float)
    ru = np.asarray(ru, float)
    slope = np.gradient(ru, x)
    g = np.maximum(1.0, margin * np.maximum(0.0, -slope) / (kp * ru))
    return ("n2c", "gain"), (x.copy(), g)


def harmonise(model: Any = None, params: ParamSet | None = None, *, platform: str = "tejas") -> Harmonised:
    """Derive the harmonised M08 tables and scalars from the nominal M07 ``model`` (default: the registry
    model)
    and the M08 ``params`` (default: ``load_fadec_params(platform)``). Deterministic (fixed grid and
    solver)."""
    from phalanx.engine.design import build_engine_model
    from phalanx.engine.layout import PI, U_A8
    from phalanx.engine.steady import TrimCondition, trim

    from .params import load_fadec_params

    model = build_engine_model() if model is None else model
    params = load_fadec_params(platform) if params is None else params
    v = params.value
    d = model.design
    # anchors (nozzle scale, idle and N1-onset demand) on the bare engine at SLS ISA, as the test-cell
    # evidence they come from; the fuel-control lines on the installed engine (nominal extraction, W2.3a)
    cond = TrimCondition(t_s=T_STD, p_s=P_STD)
    cond_inst = TrimCondition(t_s=T_STD, p_s=P_STD, bleed=float(v("harm_bleed")), pto=float(v("harm_pto")))
    n2r = float(v("n2_ref"))
    deg = np.rad2deg
    pla_gi = float(deg(v("pla_gi")))
    pla_n1 = float(deg(v("harm_n1_onset_pla")))
    pla_irp = float(deg(v("pla_irp")))
    idle_n2 = float(v("harm_idle_n2"))

    # ---- 1. variable geometry: M07's reference schedules on M08's axes
    tb = model.tables
    fvg = (("n1c", "fvg_deg"), (np.asarray(tb.fvg_x, float).copy(), deg(np.asarray(tb.fvg_y, float))))
    rebase = float(d.derived["n2c_des_rpm"]) / 16810.0
    cvg = (("n2c25", "cvg_deg"), (np.asarray(tb.cvg_x, float) * rebase, deg(np.asarray(tb.cvg_y, float))))

    # ---- 2.+3. nozzle floor scale and the N1-onset anchor. The SLS closed-loop equilibrium at the onset PLA
    # with a demand beyond reach has the N1 regulator in control; with the nozzle floor provisionally at M07's
    # MIL throat (a smaller nozzle than that point needs), the T5 loop opens the nozzle until T5 is on target:
    # that throat A8* is where N1 and T5 reach their limits together. The floor is scaled so it equals A8* at
    # the onset PLA, so NL and T5 reach their limits together "just prior to IRP" (CR-1998-208416 §7.2) and
    # the throttle map has no jump (a floor below A8* there makes T5, not N1, bind first on the floor; above
    # it the T5 loop runs the nozzle open to the N1 limit: a step in N1 between two neighbouring PLAs). Clamps
    # = M07's actuator stops.
    a8_x = deg(np.asarray(v("a8_pla_x"), float))
    a8_y = np.asarray(v("a8_pla_y"), float)  # m^2 (-400 values)
    a8_mil = float(d.stations["a8"])
    base = FadecConfig.build(params)
    vg_tables = {
        "fvg_x": fvg[1][0],
        "fvg_y": np.deg2rad(fvg[1][1]),
        "cvg_x": cvg[1][0],
        "cvg_y": np.deg2rad(cvg[1][1]),
    }

    def nozzle_of(scale: float) -> dict[str, float]:
        return {
            "a8_scale": scale,
            "a8_min": float(model.p[PI["a8_min"]]) / scale,
            "a8_max": float(model.p[PI["a8_max"]]) / scale,
        }

    provisional = a8_mil / _interp(pla_irp, a8_x, a8_y)
    reach = _with(base, {**vg_tables, "n2c_pla_y": np.full_like(base.tables.n2c_pla_y, 1.5)},
                  nozzle_of(provisional))  # fmt: skip
    r_idle = trim(model, cond, ("n2", idle_n2 * n2r), a8=_interp(pla_gi, a8_x, a8_y) * provisional)
    if not r_idle.converged:
        raise RuntimeError("harmonise: M07 ground-idle anchor trim did not converge")
    op_n1 = operating_point(model, reach, pla_n1, cond, x0=r_idle.x)
    if op_n1.regime != L_N1:
        raise RuntimeError(f"harmonise: the N1-onset anchor is held by regulator {op_n1.regime}, not N1")
    if op_n1.nozzle_t5:
        a8_star = float(op_n1.engine.u[U_A8])
        a8_scale = a8_star / _interp(pla_n1, a8_x, a8_y)
    else:  # T5 stays below its target at the N1 limit even on the MIL throat: keep the MIL-throat floor
        a8_star = float(op_n1.engine.u[U_A8])
        a8_scale = provisional
    nozzle = nozzle_of(a8_scale)
    a8_min_in2 = nozzle["a8_min"] / IN2
    a8_max_in2 = nozzle["a8_max"] / IN2

    def floor(pla: float) -> float:
        return _interp(pla, a8_x, a8_y) * a8_scale

    # the idle anchor on the final floor
    r_idle = trim(model, cond, ("n2", idle_n2 * n2r), a8=floor(pla_gi), x0=r_idle.x)
    if not r_idle.converged:
        raise RuntimeError("harmonise: M07 ground-idle anchor trim did not converge")
    sx = deg(np.asarray(v("n2c_pla_shape_x"), float))
    sy = np.asarray(v("n2c_pla_shape_y"), float)
    y_idle = _point(r_idle, pla_gi).n2c25
    y_n1 = _point(op_n1.engine, pla_n1).n2c25
    s_gi, s_n1 = _interp(pla_gi, sx, sy), _interp(pla_n1, sx, sy)
    n2c_y = y_idle + (sy - s_gi) * ((y_n1 - y_idle) / (s_n1 - s_gi))
    n2c_pla = (("pla_deg", "n2c25"), (sx.copy(), n2c_y))

    # ---- operating line of the installed engine: closed-loop equilibria from ground idle to the N1-limit
    # onset PLA (governor in control, nozzle on its floor or held by the T5 loop, VG on schedule)
    sched = _with(base, {**vg_tables, "n2c_pla_y": n2c_y}, nozzle)
    line: list[LinePoint] = []
    x = r_idle.x
    x_idle_inst = None
    for pla in np.linspace(pla_gi, pla_n1, N_LINE):
        op = operating_point(model, sched, float(pla), cond_inst, x0=x)
        if not op.converged:
            raise RuntimeError(f"harmonise: M07 line point at PLA {pla:.2f} did not converge")
        x = op.engine.x
        x_idle_inst = x if x_idle_inst is None else x_idle_inst
        line.append(_point(op.engine, float(pla)))
    lx25 = np.array([p.n2c25 for p in line])
    lx1 = np.array([p.n2c1 for p in line])
    ln1 = np.array([p.n1c1 for p in line])
    l_ru = np.array([p.ru_pph_psi for p in line])
    for name, arr in (("N2/sqrt(theta25)", lx25), ("N2/sqrt(theta1)", lx1), ("N1/sqrt(theta1)", ln1)):
        if np.any(np.diff(arr) <= 0):
            raise RuntimeError(f"harmonise: the M07 operating line is not monotonic in {name}")

    # ---- 4. ratio units: the line; below idle M07's installed steady line at the idle nozzle floor down to
    # harm_line_min_n2c (sub-idle equilibria: the fuel the engine needs to hold each N2, VG on schedule); the
    # W1.3b shape scaled to join it below that and above the N1-limit onset
    sub = sub_idle_line(model, cond_inst, floor(pla_gi), lx1[0], float(v("harm_line_min_n2c")), x_idle_inst)
    sx = np.array([q.n2c1 for q in sub])
    s_ru = np.array([q.ru_pph_psi for q in sub])
    rsx = np.asarray(v("ru_ref_shape_x"), float)
    rsy = np.asarray(v("ru_ref_shape_y"), float) / RU_SI
    x_lo = sx[0] if sx.size else lx1[0]
    y_lo = s_ru[0] if sx.size else l_ru[0]
    lo_scale = y_lo / _interp(x_lo, rsx, rsy)
    hi_scale = l_ru[-1] / _interp(lx1[-1], rsx, rsy)
    below = rsx < x_lo - 1e-6
    above = rsx > lx1[-1] + 1e-6
    ru_ref = (
        ("n2c", "ru_pph_psi"),
        (np.concatenate([rsx[below], sx, lx1, rsx[above]]), np.concatenate([rsy[below] * lo_scale, s_ru, l_ru,
                                                                              rsy[above] * hi_scale])),
    )  # fmt: skip
    # feed-forward vs the demanded N2/sqrt(theta25): flat outside the line (below it the start logic governs;
    # above it the N1 regulator is in control and the feed-forward only has to stay above the N1-limited fuel)
    y_lo, y_hi = float(n2c_y.min()), float(n2c_y.max())
    ff_x = np.concatenate(
        [[y_lo] if y_lo < lx25[0] - 1e-6 else [], lx25, [y_hi] if y_hi > lx25[-1] + 1e-6 else []]
    )
    ff_y = np.concatenate(
        [[l_ru[0]] if y_lo < lx25[0] - 1e-6 else [], l_ru, [l_ru[-1]] if y_hi > lx25[-1] + 1e-6 else []]
    )
    ru_ff = (("n2c25", "ru_pph_psi"), (ff_x, ff_y))

    # ---- 5. on-board model along the line (theta1-corrected)
    tables = {
        "fvg_n1c": fvg,
        "cvg_n2c": cvg,
        "n2c_pla": n2c_pla,
        "ru_ref": ru_ref,
        "ru_ff": ru_ff,
        "obm_n1_n2": (("n2c", "n1c"), (lx1, ln1)),
        "obm_pr3": (("n2c", "ps3_over_p0"), (lx1, np.array([p.ps3_p0 for p in line]))),
        "obm_t25": (("n1c", "t25_over_t1"), (ln1, np.array([p.t25_t1 for p in line]))),
        "obm_t5": (("n2c", "t5_over_t1"), (lx1, np.array([p.t5_t1 for p in line]))),
        "gov_ks": governor_gain_schedule(
            np.concatenate([sx, lx1]),
            np.concatenate([s_ru, l_ru]),
            float(v("gov_kp")),
            float(v("gov_ks_margin")),
        ),
    }
    scalars = {"a8_scale": a8_scale, "a8_min": a8_min_in2, "a8_max": a8_max_in2}
    anchors = {
        "sub_idle_points": float(len(sub)),
        "idle_n2c25": y_idle,
        "n1_onset_n2c25": y_n1,
        "n1_onset_n1": _point(op_n1.engine, pla_n1).n1,
        "n1_onset_a8_m2": _point(op_n1.engine, pla_n1).a8_m2,
        "a8_mil_m2": a8_mil,
        "a8_star_m2": a8_star,
    }
    return Harmonised(tables, scalars, tuple(line), anchors, tuple(sub))


def csv_text(head: tuple[str, ...], cols: tuple[np.ndarray, ...]) -> str:
    """CSV text of a derived table (fixed decimals: deterministic and diff-friendly)."""
    lines = [",".join(head)]
    for row in zip(*cols, strict=True):
        lines.append(",".join(f"{float(c):.{CSV_DECIMALS}f}" for c in row))
    return "\n".join(lines) + "\n"


#: CSV table name -> (layout.Tables x field, y field) of the kernel tables a harmonisation replaces
_TABLE_FIELDS = {
    "fvg_n1c": ("fvg_x", "fvg_y"),
    "cvg_n2c": ("cvg_x", "cvg_y"),
    "n2c_pla": ("n2c_pla_x", "n2c_pla_y"),
    "ru_ref": ("ru_x", "ru_y"),
    "ru_ff": ("ruff_x", "ruff_y"),
    "obm_pr3": ("obm_pr3_x", "obm_pr3_y"),
    "obm_t25": ("obm_t25_x", "obm_t25_y"),
    "obm_t5": ("obm_t5_x", "obm_t5_y"),
    "gov_ks": ("govk_x", "govk_y"),
}
#: CSV units -> kernel SI factors per (x, y) column (deg -> rad for PLA/VG; lb/h/psi -> (kg/s)/Pa for RU)
_DEG = float(np.pi / 180.0)
_TABLE_SI = {"fvg_n1c": (1.0, _DEG), "cvg_n2c": (1.0, _DEG), "n2c_pla": (_DEG, 1.0), "ru_ref": (1.0, RU_SI),
             "ru_ff": (1.0, RU_SI)}  # fmt: skip


def config_from(h: Harmonised, cfg: FadecConfig) -> FadecConfig:
    """A FADEC configuration that runs the derived tables and scalars of ``h`` (everything else from ``cfg``):
    what the committed CSVs and M08.yaml give after ``write_harmonised``, without writing them (sweeps of the
    design condition, negative controls). Values are not rounded to the CSV resolution."""
    tabs: dict[str, np.ndarray] = {}
    for name, (fx, fy) in _TABLE_FIELDS.items():
        _head, (x, y) = h.tables[name]
        kx, ky = _TABLE_SI.get(name, (1.0, 1.0))
        tabs[fx] = np.asarray(x, float) * kx
        tabs[fy] = np.asarray(y, float) * ky
    _h, (n2, n1) = h.tables["obm_n1_n2"]
    tabs["obm_n1_x"], tabs["obm_n1_y"] = np.asarray(n2, float), np.asarray(n1, float)
    tabs["obm_n2_x"], tabs["obm_n2_y"] = np.asarray(n1, float), np.asarray(n2, float)
    sc = h.scalars
    return _with(
        cfg, tabs, {"a8_scale": sc["a8_scale"], "a8_min": sc["a8_min"] * IN2, "a8_max": sc["a8_max"] * IN2}
    )


def write_harmonised(h: Harmonised, out_dir: Path) -> list[Path]:
    """Write the derived tables to ``out_dir`` (the platform's ``params/M08`` folder); returns the paths. The
    scalars go into M08.yaml with their provenance (the drift test checks them)."""
    out = []
    for name, (head, cols) in h.tables.items():
        p = Path(out_dir) / f"{name}.csv"
        p.write_text(csv_text(head, cols), encoding="utf-8")
        out.append(p)
    return out


__all__ = [
    "CSV_DECIMALS",
    "SUB_IDLE_STEP",
    "Harmonised",
    "LinePoint",
    "config_from",
    "csv_text",
    "governor_gain_schedule",
    "harmonise",
    "sub_idle_line",
    "write_harmonised",
]
