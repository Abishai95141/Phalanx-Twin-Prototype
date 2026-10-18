"""Steady state = equilibrium of the dynamic model (architecture §6 M07; acceptance A3), sweeps,
linearisation.

The steady solver finds the state where every continuous derivative of ``kernel.deriv`` is zero for given
inputs (actuators at their commanded positions, metal and oil temperatures at their equilibria). It is the
*same* function the integrator advances, so a run started at the solution stays put (tested). Jacobians are
complex step through the compiled kernel source (AD-34; exact to rounding). Newton with step limiting and
backtracking; continuation in fuel flow for points far from the design point (``operating_line``).

``linearize`` returns the continuous-time small-signal model (A, B, C, D) about an equilibrium for W2.3's
PWL/LPV usage-mode surrogate, with named states, inputs and outputs. The maps are piecewise linear in speed,
so a linearisation is valid within the map cell of its operating point.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

import numpy as np

from .design import EngineModel
from .layout import (
    AB_OFF,
    AUX_NAMES,
    NAUX,
    NU,
    NX,
    U_A8,
    U_NAMES,
    U_PS,
    U_TFUEL,
    U_TS,
    U_VG1,
    U_VG2,
    U_WF,
    U_WFAB,
    X_A8,
    X_N1,
    X_N2,
    X_NAMES,
    X_P3,
    X_P5,
    X_P6,
    X_P21,
    X_P45,
    X_T41,
    X_TC,
    X_TM,
    X_TOIL,
    X_VG1,
    X_VG2,
    X_WFAB,
    X_WFM,
)
from .layout import PI as _PI
from .maps import interp1
from .topology import kernel_functions

_A_N1C = AUX_NAMES.index("n1c")
_A_N2C = AUX_NAMES.index("n2c")

# unknowns of the equilibrium problem (actuators are set to their commands)
SOLVE_IDX = np.array([X_N1, X_N2, X_P21, X_P3, X_P45, X_P5, X_P6, X_T41, X_TM, X_TC, X_TOIL], dtype=np.int64)


@dataclass(frozen=True)
class SteadyResult:
    x: np.ndarray  # (NX,) equilibrium state
    aux: np.ndarray  # (NAUX,) diagnostics at the equilibrium
    u: np.ndarray  # (NU,) inputs (wf replaced by the solved value in target mode)
    converged: bool
    iterations: int
    residual: float  # max |dx/dt| / scale over the solved states (1/s)

    def aux_dict(self) -> dict[str, float]:
        return {n: float(v) for n, v in zip(AUX_NAMES, self.aux, strict=True)}


def design_inputs(model: EngineModel, **overrides: float) -> np.ndarray:
    """Input row at the design condition (SLS ISA, dry, design MIL fuel and nozzle, VG on reference)."""
    st = model.design.stations
    u = np.zeros(NU)
    u[U_WF] = st["wf"]
    u[U_A8] = st["a8"]
    u[U_VG1], u[U_VG2] = model.design.vg_ref
    u[U_TS] = 288.15
    u[U_PS] = 101325.0
    u[U_TFUEL] = 288.15 + model.p[_PI["dt_fuel_sink"]]  # fuel inlet temperature default (M09 provides it)
    for k, v in overrides.items():
        u[U_NAMES.index(k)] = v
    return u


def design_state(model: EngineModel) -> np.ndarray:
    """The design-point state vector (an equilibrium of the dynamics at ``design_inputs``)."""
    st = model.design.stations
    d = model.design.derived
    x = np.zeros(NX)
    x[X_N1], x[X_N2] = st["n1"], st["n2"]
    x[X_P21], x[X_P3], x[X_P45], x[X_P5], x[X_P6] = st["p21"], st["p3"], st["p45"], st["p5"], st["p6"]
    x[X_T41] = st["t41"]
    x[X_WFM] = st["wf"]
    x[X_A8] = st["a8"]
    x[X_VG1], x[X_VG2] = model.design.vg_ref
    x[X_TM], x[X_TC] = d["tm_ref"], d["tc_ref"]
    p = model.p
    ua = p[_PI["ua_oil_air"]] + p[_PI["ua_oil_fuel"]]
    x[X_TOIL] = 288.15 + p[_PI["dt_fuel_sink"]] + p[_PI["q_oil_ref"]] / ua
    return x


def _scale(model: EngineModel) -> np.ndarray:
    x = design_state(model)
    s = np.abs(x)
    s[X_TM] = s[X_TC] = s[X_TOIL] = s[X_T41] = 1000.0
    return s[SOLVE_IDX]


def _clamp(v: float, lo: float, hi: float) -> float:
    return lo if v < lo else hi if v > hi else v


def _actuators(model: EngineModel, x: np.ndarray, u: np.ndarray, ab_state: int) -> None:
    p = model.p
    x[X_WFM] = max(u[U_WF], 0.0)
    x[X_A8] = _clamp(u[U_A8], p[_PI["a8_min"]], p[_PI["a8_max"]])
    x[X_VG1] = _clamp(u[U_VG1], p[_PI["vg_min"]], p[_PI["vg_max"]])
    x[X_VG2] = _clamp(u[U_VG2], p[_PI["vg_min"]], p[_PI["vg_max"]])
    x[X_WFAB] = max(u[U_WFAB], 0.0) if ab_state != AB_OFF else 0.0


def vg_reference(model: EngineModel, n1c_frac, n2c_frac):
    """Reference (map) VG schedule: FVG(N1c), CVG(N2c), fractions of the design corrected speeds (rad).
    M08's nominal schedules must equal this for the map to be on schedule (A-W1.3a-12)."""
    tb = model.tables
    return interp1(tb.fvg_x, tb.fvg_y, n1c_frac), interp1(tb.cvg_x, tb.cvg_y, n2c_frac)


def _target_value(x, aux, target):
    """Value of a steady-state target: ("x", index) reads the state, ("aux", index) a diagnostic."""
    kind, k, _ = target
    return x[k] if kind == "x" else aux[k]


def _resolve_target(target: tuple[str, float], sc: np.ndarray) -> tuple[str, int, float, float]:
    """(kind, index, value, scale) of a target given by name: a state (``layout.X_NAMES``, e.g. "n2") or a
    diagnostic (``layout.AUX_NAMES``, e.g. "n2c" = N2/sqrt(theta25) in rpm, "ps3", "t5")."""
    name, val = str(target[0]), float(target[1])
    if name in X_NAMES:
        k = X_NAMES.index(name)
        if k not in SOLVE_IDX:
            raise ValueError(f"steady-state target {name!r} is an actuator state (set it through u)")
        return "x", k, val, float(sc[list(SOLVE_IDX).index(k)])
    if name in AUX_NAMES:
        return "aux", AUX_NAMES.index(name), val, max(abs(val), 1e-12)
    raise ValueError(f"unknown steady-state target {name!r} (a state or diagnostic name)")


def _residual(model, pv, z, u, ab_state, flame, sc, x_base, target, vg_schedule=True):
    """Scaled residual; z = unknowns / scale (+ wf as the last entry in target mode). Complex-safe.

    With ``vg_schedule`` the VG positions follow the reference schedule at the current corrected speeds (the
    nominal FADEC schedule), evaluated in a first pass. ``target`` = (kind, index, value, scale) from
    ``_resolve_target`` frees the fuel flow to hit a state or diagnostic value."""
    dt = np.result_type(z.dtype, np.float64)
    x = x_base.astype(dt)
    n = SOLVE_IDX.size
    x[SOLVE_IDX] = z[:n] * sc
    uu = u.astype(dt)
    if target is not None:
        wf = z[n] * model.design.stations["wf"]
        uu[U_WF] = wf
        x[X_WFM] = wf
    deriv_point = kernel_functions(model)[1]  # topology hook (AD-43): mixed_ab -> kernel.deriv_point
    if vg_schedule:
        _, aux0 = deriv_point(x, ab_state, flame, 0, 0.0, uu, pv, model.tables, -1.0)
        d = model.design.derived
        v1, v2 = vg_reference(model, aux0[_A_N1C] / d["n1c_des_rpm"], aux0[_A_N2C] / d["n2c_des_rpm"])
        x[X_VG1], x[X_VG2] = v1, v2
        uu[U_VG1], uu[U_VG2] = v1, v2
    dx, aux = deriv_point(x, ab_state, flame, 0, 0.0, uu, pv, model.tables, -1.0)
    r = dx[SOLVE_IDX] / sc
    if target is not None:
        _kind, _k, val, scale = target
        r = np.append(r, (_target_value(x, aux, target[:3]) - val) / scale)
    return r, aux, x


def steady_state(
    model: EngineModel,
    u: np.ndarray,
    *,
    x0: np.ndarray | None = None,
    ab_state: int = AB_OFF,
    flame: int = 1,
    target: tuple[str, float] | None = None,
    tol: float = 1e-11,
    max_iter: int = 60,
    vg_schedule: bool = True,
) -> SteadyResult:
    """Equilibrium for inputs ``u``. ``target=(name, value)`` frees the fuel flow to hit a value of a state
    (``"n1"``, ``"n2"``, rad/s) or of a diagnostic (``layout.AUX_NAMES``: e.g. ``"n2c"`` = N2/sqrt(theta25)
    in rpm, ``"n1c"``, ``"ps3"`` in Pa, ``"t5"`` in K). ``vg_schedule=True`` puts the VG on the reference
    schedule (nominal control); False holds ``u``'s VG."""
    u = np.asarray(u, float).copy()
    x_base = (design_state(model) if x0 is None else np.asarray(x0, float)).copy()
    _actuators(model, x_base, u, ab_state)
    sc = _scale(model)
    tgt = None
    z = x_base[SOLVE_IDX] / sc
    if target is not None:
        tgt = _resolve_target(target, sc)
        z = np.append(z, u[U_WF] / model.design.stations["wf"])
    args = (u, ab_state, flame, sc, x_base, tgt, vg_schedule)
    # phase 1 with the stoichiometric burn cap relaxed (it is inactive at any normal equilibrium but its zero
    # slope can trap Newton iterates); phase 2 polishes with the true model, so the result is an exact
    # equilibrium of the kernel in either case
    relaxed = model.p.copy()
    relaxed[_PI["f_stoich"]] = 10.0
    z, r, aux, x, it1 = _newton(model, relaxed, z, args, tol, max_iter)
    z, r, aux, x, it2 = _newton(model, model.p, z, args, tol, max_iter)
    it = it1 + it2
    res = float(np.max(np.abs(r)))
    uo = u.copy()
    if tgt is not None:
        uo[U_WF] = float(np.real(x[X_WFM]))
    if vg_schedule:
        uo[U_VG1], uo[U_VG2] = float(np.real(x[X_VG1])), float(np.real(x[X_VG2]))
    return SteadyResult(np.real(x).copy(), np.real(aux).copy(), uo, res < max(tol, 1e-8), it, res)


def _newton(model, pv, z, args, tol, max_iter):
    h = 1e-30
    r, aux, x = _residual(model, pv, z, *args)
    it = 0
    for it in range(1, max_iter + 1):
        nrm = float(np.max(np.abs(r)))
        if nrm < tol:
            it -= 1
            break
        m = z.size
        J = np.empty((m, m))
        for j in range(m):
            zc = z.astype(np.complex128)
            zc[j] += 1j * h
            rc, _, _ = _residual(model, pv, zc, *args)
            J[:, j] = rc.imag / h
        try:
            step = np.linalg.solve(J, -r)
        except np.linalg.LinAlgError:
            step = np.linalg.lstsq(J, -r, rcond=None)[0]
        # limit relative steps to 20 % of the scaled unknowns; backtrack on the residual norm
        lim = 0.2 * np.maximum(np.abs(z), 0.05)
        fac = min(1.0, float(np.min(lim / np.maximum(np.abs(step), 1e-300))))
        for _ in range(30):
            zn = z + fac * step
            rn, auxn, xn = _residual(model, pv, zn, *args)
            if np.all(np.isfinite(rn)) and float(np.max(np.abs(rn))) < nrm * (1.0 - 1e-4 * fac):
                break
            fac *= 0.5
        z, r, aux, x = zn, rn, auxn, xn
    return z, r, aux, x, it


def operating_line(
    model: EngineModel, u: np.ndarray, wf_values, *, x0: np.ndarray | None = None, n_sub: int = 4, **kw
) -> list[SteadyResult]:
    """Steady states along a fuel-flow sweep with continuation (each solve starts from the previous one,
    approached in ``n_sub`` sub-steps from the previous fuel flow). Inputs other than wf are held."""
    out = []
    x = design_state(model) if x0 is None else np.asarray(x0, float)
    wf_prev = float(u[U_WF]) if x0 is not None else model.design.stations["wf"]
    for wf in wf_values:
        for s in range(1, n_sub + 1):
            ui = np.asarray(u, float).copy()
            ui[U_WF] = wf_prev + (wf - wf_prev) * s / n_sub
            r = steady_state(model, ui, x0=x, **kw)
            x = r.x
        out.append(r)
        wf_prev = wf
    return out


def ambient_inputs(
    model: EngineModel, *, t_s: float, p_s: float, mach: float = 0.0, **kw: float
) -> np.ndarray:
    """Design inputs at another flight condition (helper for sweeps)."""
    u = design_inputs(model, **kw)
    u[U_TS] = t_s
    u[U_PS] = p_s
    if "t_fuel" not in kw:
        u[U_TFUEL] = t_s + model.p[_PI["dt_fuel_sink"]]
    u[U_NAMES.index("mach")] = mach
    return u


# trim at a condition (W2.1 F1) ------------------------------------------------------------------------------
@dataclass(frozen=True)
class TrimCondition:
    """Flight condition and exogenous inputs of one engine at a trim (SI; the M07 input ports).

    ``t_fuel`` None means the default fuel-inlet temperature ``t_s + dt_fuel_sink`` (as ``ambient_inputs``);
    ``w_engine`` are the five process-disturbance columns (AD-32, AD-46) held constant, ``health`` the ten
    ``health.engine`` deltas."""

    t_s: float = 288.15
    p_s: float = 101325.0
    mach: float = 0.0
    q_spec: float = 0.0
    w_engine: tuple[float, ...] = (0.0, 0.0, 0.0, 0.0, 0.0)
    bleed: float = 0.0
    pto: float = 0.0
    t_fuel: float | None = None
    health: tuple[float, ...] = (0.0,) * 10

    def inputs(self, model: EngineModel, *, a8: float | None = None, vg=None) -> np.ndarray:
        """The M07 input row of this condition: nozzle ``a8`` (default the design MIL throat), VG ``vg`` (IGV,
        VSV; default the design reference, replaced by the schedule in a scheduled trim), fuel from the
        design point (freed by the trim target)."""
        u = ambient_inputs(model, t_s=self.t_s, p_s=self.p_s, mach=self.mach)
        u[U_NAMES.index("q_spec")] = self.q_spec
        w = np.asarray(self.w_engine, float)
        h = np.asarray(self.health, float)
        if w.shape != (5,) or h.shape != (10,):
            raise ValueError("w_engine needs 5 columns and health 10")
        lo = U_NAMES.index("w_fuel_metering")
        u[lo : lo + 5] = w
        u[U_NAMES.index("h_fan_eta") :] = h
        u[U_NAMES.index("bleed_extract")] = self.bleed
        u[U_NAMES.index("pto_power")] = self.pto
        if self.t_fuel is not None:
            u[U_TFUEL] = self.t_fuel
        if a8 is not None:
            u[U_A8] = float(a8)
        if vg is not None:
            u[U_VG1], u[U_VG2] = (float(v) for v in vg)
        return u


def _blend(u0: np.ndarray, u1: np.ndarray, lam: float) -> np.ndarray:
    """Continuation path between two input rows: ambient pressure geometrically, everything else linearly."""
    u = (1.0 - lam) * u0 + lam * u1
    u[U_PS] = float(np.exp((1.0 - lam) * np.log(u0[U_PS]) + lam * np.log(u1[U_PS])))
    return u


def trim(
    model: EngineModel,
    condition: TrimCondition,
    target: tuple[str, float],
    *,
    a8: float | None = None,
    vg=None,
    x0: np.ndarray | None = None,
    ab_state: int = AB_OFF,
    steps: int = 12,
    max_depth: int = 5,
    step_iter: int = 25,
    direct: bool = True,
) -> SteadyResult:
    """M07 equilibrium at ``condition`` with the fuel flow freed to meet ``target`` (W2.1 F1).

    ``target`` is any ``steady_state`` target, e.g. ("n2", rad/s), ("n1", rad/s), ("n2c", rpm, i.e.
    N2/sqrt(theta25)) or ("ps3", Pa). ``a8`` is the nozzle-area command (default: the design MIL throat);
    ``vg`` = None puts the VG on the reference schedule (the nominal FADEC schedule, ``vg_reference``), a pair
    holds (IGV, VSV) fixed.

    A direct Newton solve is tried from ``x0`` (default the design state; ``direct=False`` skips it). If it
    does not converge, the solve follows a continuation path from the design point (design inputs and the
    target quantity's design value) to the requested condition and target in ``steps`` stages (``step_iter``
    Newton iterations each), halving a stage that fails (up to ``max_depth`` times): an exact equilibrium of
    the kernel in either case (``converged`` says whether it was reached). Deterministic (no randomness; fixed
    iteration schedule)."""
    u1 = condition.inputs(model, a8=a8, vg=vg)
    sched = vg is None
    first = None
    if direct:
        first = steady_state(model, u1, x0=x0, target=target, ab_state=ab_state, vg_schedule=sched)
        if first.converged:
            return first
    # continuation from the design point
    u0 = design_inputs(model)
    x = design_state(model)
    deriv_point = kernel_functions(model)[1]  # topology hook (AD-43)
    _, aux_d = deriv_point(x, AB_OFF, 1, 0, 0.0, u0, model.p, model.tables, -1.0)
    kind, k, val1, _ = _resolve_target(target, _scale(model))
    val0 = float(np.real(x[k] if kind == "x" else aux_d[k]))
    if vg is not None:  # a fixed VG is blended from the design reference
        u0[U_VG1], u0[U_VG2] = model.design.vg_ref
    lam, step = 0.0, 1.0 / steps
    last = None
    depth = 0
    while lam < 1.0 - 1e-12:
        nxt = min(1.0, lam + step)
        ul = _blend(u0, u1, nxt)
        tl = (target[0], (1.0 - nxt) * val0 + nxt * val1)
        r = steady_state(model, ul, x0=x, target=tl, ab_state=ab_state, vg_schedule=sched, max_iter=step_iter)
        if r.converged:
            x, lam, last = r.x, nxt, r
            depth = max(0, depth - 1)
            step = min(1.0 / steps, 2.0 * step) if depth == 0 else step
            continue
        depth += 1
        if depth > max_depth:
            break
        step *= 0.5
    if last is None:
        if first is None:
            return steady_state(model, u1, x0=x0, target=target, ab_state=ab_state, vg_schedule=sched)
        return first
    if lam < 1.0 - 1e-12:  # stopped on the way: an equilibrium of another condition, so not converged
        return replace(last, converged=False)
    return last


# linearisation ----------------------------------------------------------------------------------------------
LIN_INPUTS = (
    "wf_cmd",
    "a8_cmd",
    "vg_igv_cmd",
    "vg_vsv_cmd",
    "w_fuel_metering",
    "w_combustor_eff",
    "w_inlet_recovery",
    "w_shaft_load",
    "w_fan_face",
)
LIN_OUTPUTS = ("n1", "n2", "t5", "ps3", "p5", "w2", "fn", "t3", "t41_ad")


def linearize(
    model: EngineModel, ss: SteadyResult, *, ab_state: int = AB_OFF, flame: int = 1
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, tuple, tuple, tuple]:
    """Continuous-time Jacobians at an equilibrium by complex step: dx/dt = A dx + B du, dy = C dx + D du.

    The transport delay is not part of (A, B) (it is a pure delay of ``model.n_delay`` ticks on wf)."""
    h = 1e-30
    deriv_point = kernel_functions(model)[1]  # topology hook (AD-43)
    x0, u0 = ss.x, ss.u
    yidx = [AUX_NAMES.index(n) if n in AUX_NAMES else None for n in LIN_OUTPUTS]
    A = np.zeros((NX, NX))
    C = np.zeros((len(LIN_OUTPUTS), NX))
    for j in range(NX):
        xc = x0.astype(np.complex128)
        xc[j] += 1j * h
        dx, aux = deriv_point(
            xc, ab_state, flame, 0, 0.0, u0.astype(np.complex128), model.p, model.tables, -1.0
        )
        A[:, j] = dx.imag / h
        C[:, j] = [(_y(aux, xc, n, k)).imag / h for n, k in zip(LIN_OUTPUTS, yidx, strict=True)]
    B = np.zeros((NX, len(LIN_INPUTS)))
    D = np.zeros((len(LIN_OUTPUTS), len(LIN_INPUTS)))
    for j, name in enumerate(LIN_INPUTS):
        uc = u0.astype(np.complex128)
        uc[U_NAMES.index(name)] += 1j * h
        xc = x0.astype(np.complex128)
        dx, aux = deriv_point(xc, ab_state, flame, 0, 0.0, uc, model.p, model.tables, -1.0)
        B[:, j] = dx.imag / h
        D[:, j] = [(_y(aux, xc, n, k)).imag / h for n, k in zip(LIN_OUTPUTS, yidx, strict=True)]
    return A, B, C, D, X_NAMES, LIN_INPUTS, LIN_OUTPUTS


def _y(aux, x, name, k):
    if name == "n1":
        return x[X_N1]
    if name == "n2":
        return x[X_N2]
    return aux[k]


assert NAUX == len(AUX_NAMES)
