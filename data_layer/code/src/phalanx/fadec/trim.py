"""Closed-loop trim: the M07 equilibrium the M08 control law holds at a PLA and flight condition (W2.1 F1).

``operating_point(model, cfg, pla_deg, condition)`` returns the steady state at which every M08 regulator is
at its equilibrium: the fuel regulator selected by the MIN/MAX logic has zero error and every other one is on
the safe side of its limit; the nozzle sits on its PLA floor unless the T5 loop holds T5 at its target (then
the nozzle is open above the floor); the variable geometry is on M08's schedules. The engine side is solved by
``phalanx.engine.steady.trim`` (the M07 trim API), so the result is an exact equilibrium of the M07 kernel;
the M08 side needs only its commands (``initial_commands``): `Fadec(initial_wf=..., initial_a8=...,
initial_vg=...)` bootstraps its integrators from them on the first frame (bumpless start).

Steady-state equivalence of the MIN/MAX selection: at an equilibrium the selected regulator's error is zero
and every other regulator's integrator sits at its IFB equilibrium above the selected output, so the selected
one is the most restrictive, i.e. the candidate steady state with the **least fuel** among the governor target
and the limiter targets that are violated by the governor's state (N1 limit, N2 maximum, PS3 maximum). The
acceleration/deceleration schedules and the PS3 minimum (off by default, AD-50) are transient limits and do
not bind at an equilibrium. Sortie telemetry starts from post-start ground idle (AD-46): ``operating_point``
at PLA ``pla_gi`` on the ground condition.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from .codes import L_GOV_N2, L_N1, L_N2MAX, L_PS3MAX
from .layout import P_LAYOUT
from .params import FadecConfig

T_STD = 288.15
P_STD = 101325.0


@dataclass(frozen=True)
class FadecTrim:
    """An M07 equilibrium held by M08: the engine trim (``engine.x``, ``engine.u``) and M08's regime."""

    engine: Any  # phalanx.engine.steady.SteadyResult
    pla_deg: float
    regime: int  # fuel regulator code in control (codes.L_*)
    nozzle_t5: bool  # True when the nozzle T5 loop holds T5 (A8 above its floor)
    demand_n2c25: float
    a8_floor: float

    @property
    def converged(self) -> bool:
        return bool(self.engine.converged)


def _p(cfg: FadecConfig, name: str) -> float:
    return float(cfg.p[P_LAYOUT.index[name]])


def _lk(x: np.ndarray, y: np.ndarray, v: float) -> float:
    return float(np.interp(v, x, y))


def initial_commands(trim, n_engines: int = 1) -> dict[str, np.ndarray]:
    """M08 initial commands (``Fadec`` keyword arguments) from an M07 trim or a ``FadecTrim``: the fuel,
    nozzle
    and VG commands that hold the engine at it (W2.1 F1)."""
    from phalanx.engine.layout import U_A8, U_VG1, U_VG2, U_WF

    u = trim.engine.u if isinstance(trim, FadecTrim) else trim.u
    return {
        "initial_wf": np.full(n_engines, float(u[U_WF])),
        "initial_a8": np.full(n_engines, float(u[U_A8])),
        "initial_vg": np.tile([float(u[U_VG1]), float(u[U_VG2])], (n_engines, 1)),
    }


def operating_point(
    model: Any,
    cfg: FadecConfig,
    pla_deg: float,
    condition: Any = None,
    *,
    x0: np.ndarray | None = None,
    vg_iterations: int = 4,
) -> FadecTrim:
    """The M07 steady state M08 holds at ``pla_deg`` and ``condition`` (``steady.TrimCondition``; default SLS
    ISA). Below the AB range only (PLA < ``pla_ab_min``). See the module docstring for the selection rule."""
    from phalanx.engine.layout import AUX_NAMES, X_N1, X_N2
    from phalanx.engine.steady import TrimCondition, design_state, trim
    from phalanx.engine.topology import kernel_functions

    deriv_point = kernel_functions(model)[1]  # topology hook (AD-43)

    cond = TrimCondition() if condition is None else condition
    tb = cfg.tables
    pla = float(np.deg2rad(pla_deg))
    if pla >= _p(cfg, "pla_ab_min"):
        raise ValueError("operating_point covers the dry range only (PLA below the AB minimum)")
    n1r, n2r = _p(cfg, "n1_ref"), _p(cfg, "n2_ref")
    a_t2 = AUX_NAMES.index("t2")
    a_t25 = AUX_NAMES.index("t25")
    a_t5 = AUX_NAMES.index("t5")
    a_ps3 = AUX_NAMES.index("ps3")
    a_n2c = AUX_NAMES.index("n2c")
    demand = _lk(tb.n2c_pla_x, tb.n2c_pla_y, pla)
    scale = _p(cfg, "a8_scale")
    a8lo, a8hi = _p(cfg, "a8_min") * scale, _p(cfg, "a8_max") * scale
    floor = min(max(_lk(tb.a8_pla_x, tb.a8_pla_y, pla) * scale, a8lo), a8hi)
    p0 = cond.p_s
    # engine-inlet total temperature (a function of the condition only) and the N1 limit the FADEC applies
    _, aux_in = deriv_point(
        design_state(model), 0, 1, 0, 0.0, cond.inputs(model), model.p, model.tables, -1.0
    )
    t1_k = float(aux_in[a_t2])
    n1lim = min(_lk(tb.n1lim_x, tb.n1lim_y, t1_k), _p(cfg, "n1c_cap") * np.sqrt(t1_k / T_STD))

    def vg_of(res) -> tuple[float, float]:
        th1 = res.aux[a_t2] / T_STD
        th25 = res.aux[a_t25] / T_STD
        n1c = res.x[X_N1] / n1r / np.sqrt(th1)
        n2c25 = res.x[X_N2] / n2r / np.sqrt(th25)
        return _lk(tb.fvg_x, tb.fvg_y, n1c), _lk(tb.cvg_x, tb.cvg_y, n2c25)

    def solve(target: tuple[str, float], a8: float, x_start):
        """Engine trim with M08's VG schedule (fixed point over the corrected speeds)."""
        res = trim(model, cond, target, a8=a8, vg=None, x0=x_start)
        for _ in range(vg_iterations):
            if not res.converged:
                return res
            vg = vg_of(res)
            res2 = trim(model, cond, target, a8=a8, vg=vg, x0=res.x)
            if res2.converged and np.allclose(res2.x, res.x, rtol=1e-12, atol=1e-9):
                return res2
            res = res2
        return res

    def regimes(a8: float, x_start):
        """The equilibrium MIN/MAX selects at nozzle area ``a8``: the least-fuel candidate among the governor
        target and the limiter targets. The N1-limit equilibrium is solved first: when the demand is at or
        above its corrected core speed the N1 regulator is the more restrictive one (more demand needs more
        fuel) and
        the governor target, possibly beyond reach, is not solved."""
        from phalanx.engine.layout import U_WF

        x_seed = x_start
        r_n1 = solve(("n1", n1lim * n1r), a8, x_seed)
        if not r_n1.converged:
            raise RuntimeError(f"M08 operating point at PLA {pla_deg}: the N1-limit trim did not converge")
        if r_n1.aux[a_n2c] / 16810.0 <= demand:
            sel = [(L_N1, r_n1)]
        else:
            gov = solve(("n2c", demand * 16810.0), a8, x_seed)
            if not gov.converged:
                raise RuntimeError(
                    f"M08 operating point at PLA {pla_deg}: the governor trim did not converge"
                )
            sel = [(L_GOV_N2, gov)]
        base = sel[0][1]
        for code, xi, ai, target in (
            (L_N2MAX, X_N2, None, ("n2", _p(cfg, "n2_max") * n2r)),
            (L_PS3MAX, None, a_ps3, ("ps3", _p(cfg, "ps3_max"))),
        ):
            val = base.x[xi] if xi is not None else base.aux[ai]
            if val > target[1]:
                r = solve(target, a8, base.x)
                if not r.converged:
                    raise RuntimeError(
                        f"M08 operating point at PLA {pla_deg}: limiter {code} did not converge"
                    )
                sel.append((code, r))
        return min(sel, key=lambda cr: float(cr[1].u[U_WF]))

    code, res = regimes(floor, x0)
    t1 = float(res.aux[a_t2])
    t5_tgt = _lk(tb.t5lim_x, tb.t5lim_y, t1) + _p(cfg, "t5_lim_p0_k") * (_p(cfg, "p_std") - p0)
    nozzle_t5 = False
    if res.aux[a_t5] > t5_tgt:
        # the T5 loop opens the nozzle above its floor until T5 is on target: T5 falls monotonically as the
        # nozzle opens at a fixed regulator target; Illinois (safeguarded secant) iteration on A8
        lo, f_lo = floor, float(res.aux[a_t5]) - t5_tgt
        code_hi, res_hi = regimes(a8hi, res.x)
        f_hi = float(res_hi.aux[a_t5]) - t5_tgt
        nozzle_t5 = True
        if f_hi > 0.0:
            code, res = code_hi, res_hi  # nozzle fully open and T5 still above target
        else:
            hi = a8hi
            x_last = res.x
            side = 0
            for _ in range(60):
                mid = hi - f_hi * (hi - lo) / (f_hi - f_lo)
                code, res = regimes(mid, x_last)
                x_last = res.x
                f_mid = float(res.aux[a_t5]) - t5_tgt
                if abs(f_mid) < 1e-6:
                    break
                if f_mid > 0.0:
                    lo, f_lo = mid, f_mid
                    if side == -1:
                        f_hi *= 0.5
                    side = -1
                else:
                    hi, f_hi = mid, f_mid
                    if side == 1:
                        f_lo *= 0.5
                    side = 1
    return FadecTrim(res, float(pla_deg), int(code), nozzle_t5, demand, floor)


__all__ = ["FadecTrim", "initial_commands", "operating_point"]
