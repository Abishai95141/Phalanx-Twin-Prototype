"""Post-start initial conditions of the sortie (AD-46: sortie telemetry starts from post-start idle).

Two modules have no post-start initial-condition API yet, so the integration computes them here from the
modules' own models and published tables (never from a fixture), and the values enter the run's config hash
through :class:`phalanx.integration.system.SortieConfig`:

- **M07 + M08 closed-loop idle trim** (interim for W2.1b F1, ``EngineModule.trim``): the M07 equilibrium
  (``engine.steady.steady_state``) at the sortie's field conditions whose corrected core speed is the M08
  governor demand at the ground-idle PLA (``n2c_pla`` schedule, corrected by sqrt(theta25)), with the nozzle
  at M08's A8 floor at that PLA and the VG at M08's FVG/CVG schedules at the trimmed corrected speeds (a fixed
  point: the schedules depend on the trimmed state). M08 is initialised with those commands
  (``initial_wf``/``a8``/``vg``).
  This is the equilibrium of the loop *as built*, so the first seconds carry no artificial transient from a
  mismatch between M07's own VG reference and M08's schedules (the harmonisation itself is W2.1b's).
- **M04 pilot at the idle detent**: ``PilotModule`` starts with the throttle at 0 (cut-off), which would
  shut the fuel off (M08 ``pla_cutoff`` 10 deg) for the 0.1-0.3 s the pilot overlay needs to reach the
  detent. After the start the pilot's hand is at the ground-idle detent: :func:`pilot_at_idle` sets the
  throttle position, the neuromuscular-lag state and the delay buffer to the ground-idle PLA and the
  ``started`` flag, nothing else.

Both are labelled interim items (``docs/assumptions.md`` W2.1 section, A-W2.1-2 and A-W2.1-3) and are replaced
by the owning modules' APIs when they exist (W2.1b F1 for M07/M08; an M04 initial-condition API, requested).
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass

import numpy as np

from phalanx.core.state import State
from phalanx.engine.design import EngineModel
from phalanx.engine.layout import (
    AUX_NAMES,
    U_A8,
    U_BLEED,
    U_H0,
    U_MACH,
    U_PS,
    U_PTO,
    U_Q,
    U_TFUEL,
    U_TS,
    U_VG1,
    U_VG2,
    U_WF,
    X_NAMES,
)
from phalanx.engine.steady import design_inputs, steady_state

_A = {n: k for k, n in enumerate(AUX_NAMES)}
_X = {n: k for k, n in enumerate(X_NAMES)}


@dataclass(frozen=True)
class EngineTrim:
    """Closed-loop post-start idle of one engine: M07 state/inputs and the matching M08 commands."""

    x: np.ndarray  # M07 equilibrium state
    u: np.ndarray  # M07 input row at the equilibrium
    wf: float  # kg/s
    a8: float  # m^2
    vg: tuple[float, float]  # rad (FVG/IGV, CVG/VSV)
    n2_demand: float  # rad/s, the governed N2 at the trim
    iterations: int
    residual: float

    def vector(self) -> np.ndarray:
        """Flat float64 record of the trim (for the config hash)."""
        return np.concatenate([self.x, self.u, [self.wf, self.a8, *self.vg, self.n2_demand]])


def _lk(x: np.ndarray, y: np.ndarray, v: float) -> float:
    """M08's table lookup (linear, clamped; ``fadec.kernel._lk`` on real arguments)."""
    n = x.shape[0]
    if v <= x[0]:
        return float(y[0])
    if v >= x[n - 1]:
        return float(y[n - 1])
    i = 0
    while x[i + 1] < v:
        i += 1
    return float(y[i] + (v - x[i]) / (x[i + 1] - x[i]) * (y[i + 1] - y[i]))


def engine_post_start_trim(
    model: EngineModel,
    fadec_cfg,
    *,
    pla: float,
    t_s: float,
    p_s: float,
    q_spec: float,
    mach: float,
    bleed: float,
    pto: float,
    t_fuel: float,
    health: np.ndarray,
    max_fixed_point: int = 12,
) -> EngineTrim:
    """M07 equilibrium governed by M08 at ``pla`` (module docstring). Raises if it does not converge."""
    from phalanx.fadec.layout import P_LAYOUT

    tb = fadec_cfg.tables
    p8 = fadec_cfg.p
    pi = P_LAYOUT.index
    n2r = float(p8[pi["n2_ref"]])
    n1r = float(p8[pi["n1_ref"]])
    t_std = float(p8[pi["t_std"]])
    a8 = _lk(tb.a8_pla_x, tb.a8_pla_y, pla) * float(p8[pi["a8_scale"]])
    a8_lo = float(p8[pi["a8_min"]]) * float(p8[pi["a8_scale"]])
    a8_hi = float(p8[pi["a8_max"]]) * float(p8[pi["a8_scale"]])
    a8 = min(max(a8, a8_lo), a8_hi)
    dem_c = _lk(tb.n2c_pla_x, tb.n2c_pla_y, pla)  # corrected N2 demand (N2/sqrt(theta25)), fraction of n2_ref
    u = design_inputs(model)
    u[U_TS], u[U_PS], u[U_Q], u[U_MACH] = t_s, p_s, q_spec, mach
    u[U_BLEED], u[U_PTO], u[U_TFUEL] = bleed, pto, t_fuel
    u[U_H0 : U_H0 + health.size] = np.asarray(health, dtype=np.float64)
    u[U_A8] = a8
    # continuation from the design point down to the idle speed (VG on M07's reference on the way down)
    d = model.design.stations
    x = None
    t25 = t_s
    target = dem_c * n2r * math.sqrt(t25 / t_std)
    ss = None
    for f in [1.0, *np.arange(0.97, target / d["n2"] - 1e-9, -0.03), target / d["n2"]]:
        uu = u.copy()
        if f >= 0.95:
            uu[U_A8] = d["a8"]
        ss = steady_state(model, uu, x0=x, target=("n2", f * d["n2"]))
        if not ss.converged:
            raise RuntimeError(f"M07 idle continuation did not converge at {f:.3f} of design N2")
        x = ss.x
    # fixed point: governed N2 on T25, VG on M08's schedules at the trimmed corrected speeds
    it = 0
    for _ in range(max_fixed_point):
        it += 1
        aux = ss.aux
        t25 = float(aux[_A["t25"]])
        t1 = float(aux[_A["t2"]])
        target = dem_c * n2r * math.sqrt(t25 / t_std)
        n1c = float(ss.x[_X["n1"]]) / n1r / math.sqrt(t1 / t_std)
        n2c25 = float(ss.x[_X["n2"]]) / n2r / math.sqrt(t25 / t_std)
        vg = (_lk(tb.fvg_x, tb.fvg_y, n1c), _lk(tb.cvg_x, tb.cvg_y, n2c25))
        uu = u.copy()
        uu[U_VG1], uu[U_VG2] = vg
        new = steady_state(model, uu, x0=ss.x, target=("n2", target), vg_schedule=False)
        if not new.converged:
            raise RuntimeError("M07 closed-loop idle trim did not converge")
        moved = abs(float(new.x[_X["n2"]]) - float(ss.x[_X["n2"]])) + abs(
            float(new.u[U_VG2]) - float(ss.u[U_VG2])
        )
        ss = new
        if moved < 1e-9 * n2r:
            break
    return EngineTrim(
        x=ss.x.copy(),
        u=ss.u.copy(),
        wf=float(ss.u[U_WF]),
        a8=float(ss.u[U_A8]),
        vg=(float(ss.u[U_VG1]), float(ss.u[U_VG2])),
        n2_demand=float(target),
        iterations=it,
        residual=float(ss.residual),
    )


def pilot_at_idle(state: State, pla: float) -> State:
    """M04 state with the hand at the ground-idle detent after the start (module docstring)."""
    from phalanx.pilot import kernel as K

    st = {k: np.array(v, copy=True) for k, v in state.items()}
    st["f"][K.F_PLA] = pla
    st["f"][K.F_PLANM] = pla
    st["buf"][2, :] = pla
    st["i"][K.I_STARTED] = 1
    return st


def adc_at_field(state: State, p_s: float, adc_p: np.ndarray) -> State:
    """M12 avionics state whose ADC pressure altitude is that of the field static pressure ``p_s`` (the parked
    aircraft's air data before the window, AD-46). Its held ``p0_from_hp`` (M08's P0 altitude signal, read
    one frame late) is then ``p_s`` from the first FADEC frame instead of the standard sea-level pressure at
    the cold ADC's zero altitude (W2.2: "initialise the ADC before M08's first frame"); the ADC's first DFCC
    frame overwrites every output."""
    from phalanx.sensors.avionics import adc as AD
    from phalanx.sensors.avionics.module import _HP

    st = {k: np.array(v, copy=True) for k, v in state.items()}
    st["adc_f"][AD.F_OUT + _HP] = AD.pressure_altitude(float(p_s), adc_p)
    return st


def initial_condition_record(values: Mapping[str, np.ndarray | float]) -> dict[str, np.ndarray]:
    """Float64 arrays of the post-start initial conditions (stable order; for the config hash)."""
    return {k: np.atleast_1d(np.asarray(values[k], dtype=np.float64)) for k in sorted(values)}


__all__ = [
    "EngineTrim",
    "adc_at_field",
    "engine_post_start_trim",
    "initial_condition_record",
    "pilot_at_idle",
]
