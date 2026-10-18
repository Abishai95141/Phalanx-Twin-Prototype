"""TEST FIXTURE (not a deliverable): a closed-loop M05 + M06 harness with ideal sensor lanes.

W2.1 wires the real modules (M03 atmosphere, M07 thrust, M09 mass/hydraulics, M12/M13 lanes). Until then the
W1.2 closed-loop tests use this harness, which calls the two delivered kernels tick by tick in the W2.1 order
(FCS reads the airframe outputs through a one-frame delayed back-edge; the airframe reads this tick's surface
positions) and supplies the boundary inputs from labelled fixtures:

- lanes: noise-free digitised readings of the airframe truth (RSA = body rates, ASA = specific force at the
  ASA station including the lever-arm terms, vanes = alpha/beta through the nominal calibration, pressures
  from the USSA-76 fixture atmosphere and the pitot equations, inceptors = the scripted stick, surface
  positions = the previous tick's ``fcs.surf_pos`` (airbrake strokes 0), WoW discretes from af.wow), with
  per-test fault hooks; DFCC frames from ``frame_schedule`` on the DFCC acquisition clock;
- atmosphere: USSA-76 at the airframe altitude (analysis.isa); thrust: held at the trim value;
- mass properties: the published reference set; hydraulics: 280 bar on both systems unless a test overrides.

Never imported by src/. This module holds no tests itself.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass, field

import numpy as np

from phalanx.airframe.analysis import Condition, isa, make_ic, reference_mass_properties, trim
from phalanx.airframe.build import airframe_param_set, build_config
from phalanx.airframe.ic import initial_float_state
from phalanx.airframe.kernel import (
    N_I as AF_NI,
)
from phalanx.airframe.kernel import (
    O_ALPHA,
    O_ALT,
    O_BETA,
    O_FX,
    O_MACH,
    O_QBAR,
    O_WOW0,
    O_WX,
    airframe_kernel,
    airframe_outputs,
)
from phalanx.core.module import ModuleBase, ParamSet, Port
from phalanx.core.state import Field, StateSchema
from phalanx.core.time import RG_240, TRUTH_DT_S, truth_step_time_ns
from phalanx.fcs.build import build_fcs_config, fcs_param_set
from phalanx.fcs.kernel import fcs_kernel
from phalanx.fcs.layout import (
    I_NNEXT,
    N_U,
    P_BC0,
    P_BK1,
    P_VC0,
    P_VK1,
    SIG_AL,
    SIG_AOSS,
    SIG_AR,
    SIG_NY,
    SIG_NZ,
    SIG_P,
    SIG_PED,
    SIG_POS0,
    SIG_PS,
    SIG_PT,
    SIG_Q,
    SIG_R,
    SIG_SP,
    SIG_SR,
    U_AB,
    U_ALPHA,
    U_BETA,
    U_DPAV,
    U_GEAR,
    U_HEALTH,
    U_LANES,
    U_QBAR,
    U_WOW,
)
from phalanx.fcs.module import Fcs, FcsIC, frame_schedule, ic_params

G0 = 9.80665
X_ASA = 1.0  # must match M05 design x_asa


def total_pressure(ps: float, mach: float) -> float:
    if mach <= 1.0:
        return ps * (1.0 + 0.2 * mach * mach) ** 3.5
    m2 = mach * mach
    return ps * (1.2 * m2) ** 3.5 * (2.4 / (2.8 * m2 - 0.4)) ** 2.5


@dataclass
class Harness:
    """Closed loop at a trimmed condition. ``stick(t) -> (pitch, roll, pedal)``; ``lane_hook(t, u)`` may
    corrupt
    the FCS input row in place (lane faults, false WoW); ``dp_avail(t) -> (2,)`` hydraulic supply."""

    mach: float
    alt: float
    fcs_overrides: dict = field(default_factory=dict)
    stick: Callable[[float], tuple[float, float, float]] = lambda t: (0.0, 0.0, 0.0)
    lane_hook: Callable[[float, np.ndarray], None] | None = None
    dp_avail: Callable[[float], tuple[float, float]] = lambda t: (2.8e7, 2.8e7)
    gear: float = 0.0
    #: optional ``surf_hook(k, pos) -> pos``: modifies the 13 surface positions on their way from M05 to M06
    #: at tick k (E1-HY item 7: gain and delay injection at the plant input for nonlinear margins)
    surf_hook: Callable[[int, np.ndarray], np.ndarray] | None = None

    def __post_init__(self) -> None:
        aps = airframe_param_set()
        self.acfg = build_config(aps, 1)
        m, cg, j = reference_mass_properties(aps)
        self.cond = Condition(self.alt, self.mach, m, cg, j, gear=self.gear)
        tr = trim(self.acfg, self.cond, guess=(0.05 if self.mach > 0.5 else 0.2, 0.0, 30000.0))
        self.trim = tr
        ic = make_ic(self.acfg, self.cond, tr, h_ground=-1000.0)
        self.af_f = initial_float_state(
            ic.lat,
            ic.lon,
            ic.h,
            np.asarray(ic.vel_ned),
            np.asarray(ic.quat_nb),
            np.zeros(3),
            ic.gear,
            -1000.0,
            self.acfg.dp,
        )
        self.af_i = np.zeros(AF_NI, dtype=np.int64)
        self.u_af = tr.u.copy()
        fps = fcs_param_set(
            extra=ic_params(
                FcsIC(surf=tr.u[0:13].copy(), alpha=tr.alpha, mach=self.mach, hp=self.alt, on_ground=False)
            )
        )
        if self.fcs_overrides:
            fps = fps.replace(**self.fcs_overrides)
        self.fcs_params = fps
        self.fcfg = build_fcs_config(fps)
        mod = Fcs("fcs", fps)
        st = mod.init(fps, None)
        self.fc_f, self.fc_i = st["f"], st["i"]
        self.last_pos = tr.u[0:13].copy()
        self.out_af = airframe_outputs(
            self.af_f,
            self.acfg.dp,
            self.acfg.ap,
            self.acfg.tab,
            self.acfg.gtab,
            self.acfg.ttab,
            self.u_af,
            1,
            0,
        )
        self.w_prev = self.out_af[O_WX : O_WX + 3].copy()
        self.wdot = np.zeros(3)
        self.k = 0

    def lanes_row(self, t: float) -> np.ndarray:
        o = self.out_af
        u = np.zeros(N_U)
        sp, sr, ped = self.stick(t)
        u[U_AB] = 0.0
        u[U_GEAR] = self.gear
        u[U_DPAV : U_DPAV + 2] = self.dp_avail(t)
        u[U_HEALTH : U_HEALTH + 13] = 0.0
        u[U_ALPHA], u[U_BETA], u[U_QBAR] = o[O_ALPHA], o[O_BETA], o[O_QBAR]
        w = o[O_WX : O_WX + 3]
        r = np.array([X_ASA, 0.0, 0.0])
        f_asa = o[O_FX : O_FX + 3] + np.cross(self.wdot, r) + np.cross(w, np.cross(w, r))
        _, _, _, ps = isa(o[O_ALT])
        cp = self.fcfg.p
        vals = {
            SIG_P: w[0],
            SIG_Q: w[1],
            SIG_R: w[2],
            SIG_NZ: -f_asa[2],
            SIG_NY: f_asa[1],
            # vanes read the local flow through the nominal calibration (local = k1 angle + c0, A-W1.2-25)
            SIG_AL: cp[P_VK1] * o[O_ALPHA] + cp[P_VC0],
            SIG_AR: cp[P_VK1] * o[O_ALPHA] + cp[P_VC0],
            SIG_AOSS: cp[P_BK1] * o[O_BETA] + cp[P_BC0],
            SIG_PS: ps,
            SIG_PT: total_pressure(ps, o[O_MACH]),
            SIG_SP: sp,
            SIG_SR: sr,
            SIG_PED: ped,
        }
        for s in range(11):  # rad surfaces; airbrake strokes stay 0
            vals[SIG_POS0 + s] = self.last_pos[s]
        for sig, v in vals.items():
            u[U_LANES + 4 * sig : U_LANES + 4 * sig + 4] = v
        u[U_WOW : U_WOW + 3] = o[O_WOW0 : O_WOW0 + 3]
        if self.lane_hook is not None:
            self.lane_hook(t, u)
        return u

    def tick(self) -> tuple[np.ndarray, np.ndarray]:
        t = self.k * TRUTH_DT_S
        u_fcs = self.lanes_row(t)
        c = self.fcfg
        fr, off, n_next = frame_schedule(c, int(self.fc_i[I_NNEXT]), np.array([truth_step_time_ns(self.k)]))
        self.fc_f, self.fc_i, out_f = fcs_kernel(
            self.fc_f,
            self.fc_i,
            c.p,
            c.tab,
            u_fcs[None, :],
            fr,
            off,
            TRUTH_DT_S,
            c.tf,
            c.n_sub_act,
            c.crit_mask,
        )
        self.fc_i[I_NNEXT] = n_next
        self.last_pos = out_f[0, 0:13].copy()
        u = self.u_af.copy()
        u[0:13] = out_f[0, 0:13]
        if self.surf_hook is not None:
            u[0:13] = self.surf_hook(self.k, u[0:13].copy())
        rho, a, ts, _ = isa(self.out_af[O_ALT])
        u[14 + 13], u[14 + 14], u[14 + 15] = rho, a, ts
        self.af_f, self.af_i, out_a = airframe_kernel(
            self.af_f,
            self.af_i,
            self.acfg.dp,
            self.acfg.ap,
            self.acfg.tab,
            self.acfg.gtab,
            self.acfg.ttab,
            u[None, :],
            TRUTH_DT_S,
            1,
            0,
        )
        self.out_af = out_a[0]
        w = self.out_af[O_WX : O_WX + 3]
        self.wdot = (w - self.w_prev) / TRUTH_DT_S
        self.w_prev = w.copy()
        self.k += 1
        return out_f[0], out_a[0]

    def run(self, seconds: float) -> tuple[np.ndarray, np.ndarray]:
        n = round(seconds / TRUTH_DT_S)
        of, oa = [], []
        for _ in range(n):
            a, b = self.tick()
            of.append(a)
            oa.append(b)
        return np.array(of), np.array(oa)


def nz_of(out_a: np.ndarray) -> np.ndarray:
    return -out_a[:, O_FX + 2] / G0


class SignalSource(ModuleBase):
    """TEST FIXTURE: a 240 Hz module that outputs given port values, optionally varying with the step index
    (``fn(k) -> dict`` overrides). Used to drive M05/M06 through the core scheduler."""

    version = "0"
    rate = RG_240
    state_schema = StateSchema("test.signal_source", 1, (Field("k", "<i8", ()),))

    def __init__(self, id: str, ports_like, values: dict, fn: Callable[[int], dict] | None = None) -> None:
        self.ports_out = tuple(Port(p.name, p.unit, p.dtype, p.shape) for p in ports_like)
        super().__init__(id, ParamSet(f"test.{id}", {}))
        self._vals = {
            p.name: np.asarray(values[p.name], dtype=p.dtype).reshape(p.shape) for p in self.ports_out
        }
        self._fn = fn

    def init(self, params, keys):
        return {"k": np.array(0, dtype=np.int64)}

    def _at(self, k: int) -> dict:
        v = dict(self._vals)
        if self._fn is not None:
            for name, val in self._fn(k).items():
                p = next(q for q in self.ports_out if q.name == name)
                v[name] = np.asarray(val, dtype=p.dtype).reshape(p.shape)
        return v

    def initial_outputs(self, state):
        return {k: v.copy() for k, v in self._at(0).items()}

    def step(self, state, inputs, t, dt):
        k = int(state["k"]) + 1
        return {"k": np.array(k, dtype=np.int64)}, {n: v.copy() for n, v in self._at(k).items()}


__all__ = ["Harness", "SignalSource", "math", "nz_of", "total_pressure"]
