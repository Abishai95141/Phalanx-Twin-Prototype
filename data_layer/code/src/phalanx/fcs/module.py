"""M05 FCS module: the DFCC + actuator kernel inside the §5.5 contract (``ModuleBase``).

``step`` is ``step_block`` with ``L = 1`` (bitwise identical by construction); ``compiled=False`` runs the
NumPy
reference (``py_func``). Events (``on_event``) are the fault-injection and maintenance hooks:

| kind | payload | effect |
|---|---|---|
| ``fcs.channel_fault`` | channel 0-3, subsystem 0-22, active | sets/clears an injected subsystem fault
(hidden truth); CBIT detects it |
| ``fcs.actuator_fault`` | surface 0-12, mode ``jam``/``servo``, channel 0-3 (servo), active | jams a surface,
or fails one servo coil channel |
| ``fcs.reset`` | - | pilot/ground reset: clears latched channel failures without a present critical fault,
lane failures, the reversion latch; sets CHANNEL_RESET |
| ``fcs.pbit_start`` / ``fcs.mbit_start`` | - | starts PBIT / MBIT (ground only) |
| ``ops.power_up`` | tail_no, sortie_id, engine_starts, cold_soak | M02's power-up at the engine start (W2.5):
starts PBIT, as ``fcs.pbit_start`` (M02 then sends no ``fcs.pbit_start``) |
| ``fcs.spin_mode`` | on | pilot-selectable spin-recovery mode |
| ``fcs.wow_fault`` | leg 0-2 (nose, left, right), value 0/1, active | WoW proximity switch stuck at ``value``
(hidden truth; e.g. water/ice in the strut switch) |

Frame schedule (AD-42): :func:`frame_schedule` assigns the DFCC-clock sample instants to truth steps with the
same arithmetic as M13 (``core.sampling.samples_for_steps``) and resolves the computation delay to the first
truth frame at or after ``t_sample + delay``; the next sample index is int state (``dfcc_next_sample``).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from phalanx.acquisition.module import lane_port
from phalanx.core.events import Event
from phalanx.core.module import ContractError, Inputs, ModuleBase, Outputs, Param, ParamSet
from phalanx.core.sampling import samples_for_steps
from phalanx.core.state import State
from phalanx.core.time import RG_240, latest_truth_steps, truth_step_times_ns

from .actuators import C_GNULL, C_NSEC, C_SYS
from .build import FcsConfig, build_fcs_config, fcs_param_set
from .kernel import _gains, _recorded, fcs_kernel, kernel_reference
from .layout import (
    BIT_RUNNING,
    CCDL_FAIL,
    CH_DROPOUT,
    CH_FAILED,
    CH_RESET,
    F_ALPHA,
    F_CMD,
    F_DE,
    F_DR,
    F_HP,
    F_MACH,
    F_PEND,
    F_POS,
    F_QBAR,
    F_VOTE,
    F_ZP,
    I_ACTBIT,
    I_ACTCNT,
    I_ADMIS,
    I_ADVALID,
    I_APPLY,
    I_CBCNT,
    I_CBIT,
    I_CHFLT,
    I_CHST,
    I_GROUND,
    I_JAM,
    I_LAW,
    I_LFAIL,
    I_MBIT,
    I_MBITT,
    I_MCNT,
    I_NNEXT,
    I_PBIT,
    I_PBITT,
    I_REVLATCH,
    I_RSTCNT,
    I_SERVO,
    I_SPIN,
    I_VANECNT,
    I_WOWCNT,
    I_WOWF,
    I_WOWV,
    LAW_GROUND,
    LAW_SCHEDULED,
    LAYOUT,
    N_F,
    N_I,
    N_U,
    O_CHST,
    O_FLOW,
    O_LAW,
    O_POS,
    O_RATE,
    O_REC,
    PARAM_NAMES,
    SIG_AL,
    SIG_AOSS,
    SIG_AR,
    SIG_NZ,
    SIG_POS0,
    SIG_PS,
    SIG_PT,
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
from .ports import N_SIG, N_SURF, RECORDED, VOTED_SIGNALS, lane_inputs, ports

IC_SOURCE = (
    "run configuration: sortie initial condition (set by the scenario / W2.1 wiring), not a model parameter"
)


@dataclass(frozen=True)
class FcsIC:
    """Initial DFCC/actuator condition: trimmed surfaces and the flight condition the DFCC believes."""

    surf: np.ndarray = field(default_factory=lambda: np.zeros(N_SURF))  # rad, fcs.surf_pos order
    alpha: float = 0.0  # rad
    mach: float = 0.0
    hp: float = 0.0  # pressure altitude, m
    on_ground: bool = True


def ic_params(ic: FcsIC) -> dict[str, Param]:
    def p(v, unit):
        return Param(v, unit, "ASSUMPTION", IC_SOURCE)

    s = np.asarray(ic.surf, dtype=np.float64)
    if s.shape != (N_SURF,):
        raise ContractError("FcsIC.surf needs 13 surface positions")
    return {
        "ic_surf": p(s, "rad"),
        "ic_alpha": p(float(ic.alpha), "rad"),
        "ic_mach": p(float(ic.mach), "1"),
        "ic_hp": p(float(ic.hp), "m"),
        "ic_ground": p(1 if ic.on_ground else 0, "1"),
    }


def frame_schedule(cfg: FcsConfig, n_next: int, t: np.ndarray) -> tuple[np.ndarray, np.ndarray, int]:
    """DFCC frames in the truth steps starting at ``t`` (int64 ns): ``(fr, off, next_index)``.

    ``fr[j]`` = number of DFCC samples in step ``j`` (0 or 1); ``off[j]`` = steps from ``j`` to the first
    truth frame at or after ``t_sample + delay``. ``n_next`` must be the first sample at or after ``t[0]``.
    """
    t = np.asarray(t, dtype=np.int64).reshape(-1)
    k = latest_truth_steps(t)
    ss = samples_for_steps(cfg.clock, int(n_next), t, truth_step_times_ns(k + 1))
    fr = ss.count.astype(np.int64)
    if fr.size and int(fr.max(initial=0)) > 1:
        raise ContractError("more than one DFCC frame in a truth step")
    off = np.zeros(t.size, dtype=np.int64)
    if ss.times.size:
        apply_step = latest_truth_steps(ss.times + (cfg.delay_ns - 1)) + 1
        off[ss.step] = apply_step - k[ss.step]
    return fr, off, int(ss.next_index)


def _isa_pressure(hp: float, p: np.ndarray, names) -> float:
    g0 = p[names["g0"]]
    p0, t0, lapse, r = p[names["isa_p0"]], p[names["isa_t0"]], p[names["isa_lapse"]], p[names["r_air"]]
    h11 = p[names["isa_h_trop"]]
    if hp <= h11:
        return p0 * (1.0 - lapse * hp / t0) ** (g0 / (r * lapse))
    p11 = p0 * (1.0 - lapse * h11 / t0) ** (g0 / (r * lapse))
    return p11 * math.exp(-g0 * (hp - h11) / (r * (t0 - lapse * h11)))


def _total_pressure(ps: float, mach: float, gamma: float) -> float:
    if mach <= 1.0:
        return ps * (1.0 + 0.5 * (gamma - 1.0) * mach * mach) ** (gamma / (gamma - 1.0))
    m2 = mach * mach  # Rayleigh pitot
    a = ((gamma + 1.0) * m2 / 2.0) ** (gamma / (gamma - 1.0))
    b = ((gamma + 1.0) / (2.0 * gamma * m2 - (gamma - 1.0))) ** (1.0 / (gamma - 1.0))
    return ps * a * b


class Fcs(ModuleBase):
    """Quadruplex DFCC replica (80 Hz exact frame, 8 ms delay) and the 13 hydraulic actuators."""

    version = "1.0.0"
    rate = RG_240
    state_schema = LAYOUT.schema

    def __init__(self, id: str, params: ParamSet, *, compiled: bool = True, identity=None) -> None:
        cfg = build_fcs_config(params)
        ins, outs, _ = ports(1, clock=cfg.clock)  # lane ports declare the clock the frames run on
        self.ports_in = ins
        self.ports_out = outs
        super().__init__(id, params, identity=identity)
        self.cfg = cfg
        self._kernel = fcs_kernel if compiled else kernel_reference
        self._lanes = [(U_LANES + 4 * sg + c, lane_port(cid)) for sg, c, cid in lane_inputs()]
        dtypes = {p.name: p.dtype for p in outs}
        self._rec = [(k, name, dtypes[name]) for k, name in enumerate(RECORDED)]
        missing = [k for k in ("ic_surf", "ic_alpha", "ic_mach", "ic_hp", "ic_ground") if k not in params]
        if missing:
            raise ContractError(f"{id}: ParamSet lacks initial-condition entries {missing}")

    @classmethod
    def from_registry(cls, id: str, ic: FcsIC | None = None, *, platform: str = "tejas", **kw) -> Fcs:
        return cls(id, fcs_param_set(platform, extra=ic_params(ic or FcsIC())), **kw)

    # ------------------------------------------------------------------ contract
    def init(self, params: ParamSet, keys) -> State:
        c = self.cfg
        names = {n: k for k, n in enumerate(PARAM_NAMES)}
        p = c.p
        f = np.zeros(N_F)
        i = np.zeros(N_I, dtype=np.int64)
        surf = np.asarray(params.value("ic_surf"), dtype=np.float64)
        alpha = float(params.value("ic_alpha"))
        mach = float(params.value("ic_mach"))
        hp = float(params.value("ic_hp"))
        ground = int(params.value("ic_ground")) == 1
        f[F_POS : F_POS + N_SURF] = surf
        f[F_CMD : F_CMD + N_SURF] = surf
        f[F_PEND : F_PEND + N_SURF] = surf
        for s in range(N_SURF):  # position votes; airbrake transducers read stroke (m): closed at the IC
            f[F_VOTE + SIG_POS0 + s] = surf[s] if VOTED_SIGNALS[SIG_POS0 + s][2] == "rad" else 0.0
        de = float(np.mean(surf[0:4]))
        f[F_DE] = de
        f[F_DR] = surf[4]
        ps = _isa_pressure(hp, p, names)
        f[F_VOTE + SIG_NZ] = p[names["g0"]]
        f[F_VOTE + SIG_PS] = ps
        f[F_VOTE + SIG_PT] = _total_pressure(ps, mach, p[names["gamma_air"]])
        f[F_VOTE + SIG_AL] = p[names["vane_k1"]] * alpha + p[names["vane_c0"]]
        f[F_VOTE + SIG_AR] = f[F_VOTE + SIG_AL]
        f[F_VOTE + SIG_AOSS] = p[names["aoss_c0"]]
        f[F_ALPHA] = alpha
        f[F_MACH] = mach
        f[F_HP] = hp
        f[F_QBAR] = 0.5 * p[names["gamma_air"]] * ps * mach * mach
        i[I_APPLY] = -1
        i[I_ADVALID] = 1
        i[I_NNEXT] = c.clock.first_index_at_or_after(0)  # as M13 (AcquisitionCore.init_state)
        if ground:
            i[I_LAW] = LAW_GROUND
            i[I_GROUND] = 1
            i[I_WOWCNT] = int(p[names["n_wow"]])
        else:
            i[I_LAW] = LAW_SCHEDULED
            g = np.empty(8)
            _gains(c.tab, mach, hp, g)
            if g[2] != 0.0:  # pitch integrator holds the trim elevon (dnz = 0, q = 0, command 0)
                f[F_ZP] = de / g[2]
        return {"f": f, "i": i}

    def initial_outputs(self, state: State) -> Outputs:
        f, i = state["f"], state["i"]
        a = self.cfg.tab.atab
        dp = self.cfg.p[PARAM_NAMES.index("dp_rated")]
        flow = np.zeros(2)
        for s in range(N_SURF):  # quiescent null leakage at rated pressure until the first step
            if a[s, C_NSEC] > 1.5:
                flow += a[s, C_GNULL] * dp
            else:
                flow[int(a[s, C_SYS] > 0.5)] += a[s, C_GNULL] * dp
        row = np.zeros(O_REC + len(self._rec))
        _recorded(np.asarray(f, dtype=np.float64), np.asarray(i, dtype=np.int64), row)
        out = {
            "surf_pos": np.array(f[F_POS : F_POS + N_SURF]),
            "surf_rate": np.zeros(N_SURF),
            "hyd_flow_demand": flow,
            "law_state": np.array(i[I_LAW], dtype=np.int64),
            "channel_status": np.array(i[I_CHST : I_CHST + 4], dtype=np.int64),
        }
        for k, name, dt in self._rec:
            out[name] = np.array(row[O_REC + k], dtype=dt)
        return out

    def _pack(self, inputs: Inputs, n: int) -> np.ndarray:
        u = np.zeros((n, N_U))
        u[:, U_AB] = np.reshape(inputs["airbrake_cmd"], (n,))
        u[:, U_GEAR] = np.reshape(inputs["gear_cmd"], (n,))
        u[:, U_DPAV : U_DPAV + 2] = np.reshape(inputs["hyd_dp_avail"], (n, 2))
        u[:, U_HEALTH : U_HEALTH + N_SURF] = np.reshape(inputs["health_actuator"], (n, N_SURF))
        u[:, U_ALPHA] = np.reshape(inputs["alpha"], (n,))
        u[:, U_BETA] = np.reshape(inputs["beta"], (n,))
        u[:, U_QBAR] = np.reshape(inputs["qbar"], (n,))
        for col, name in self._lanes:  # lane sample buffers of capacity 1: slot 0 (read only in frame steps)
            u[:, col] = np.reshape(inputs[name], (n, -1))[:, 0]
        u[:, U_WOW : U_WOW + 3] = np.reshape(inputs["wow"], (n, 3))
        return u

    def step_block(self, state: State, inputs: Inputs, t: np.ndarray, dt: float):
        t = np.asarray(t, dtype=np.int64).reshape(-1)
        n = int(t.size)
        c = self.cfg
        fr, off, n_next = frame_schedule(c, int(state["i"][I_NNEXT]), t)
        f, i, out = self._kernel(
            state["f"],
            state["i"],
            c.p,
            c.tab,
            self._pack(inputs, n),
            fr,
            off,
            dt,
            c.tf,
            c.n_sub_act,
            c.crit_mask,
        )
        i[I_NNEXT] = n_next
        res = {
            "surf_pos": out[:, O_POS : O_POS + N_SURF].copy(),
            "surf_rate": out[:, O_RATE : O_RATE + N_SURF].copy(),
            "hyd_flow_demand": out[:, O_FLOW : O_FLOW + 2].copy(),
            "law_state": out[:, O_LAW].astype(np.int64),
            "channel_status": out[:, O_CHST : O_CHST + 4].astype(np.int64),
        }
        for k, name, dtype in self._rec:
            res[name] = out[:, O_REC + k].astype(dtype)
        return {"f": f, "i": i}, res

    def step(self, state: State, inputs: Inputs, t: int, dt: float):
        one = {k: np.asarray(v)[None, ...] for k, v in inputs.items()}
        new, out = self.step_block(state, one, np.array([t], np.int64), dt)
        return new, {k: v[0] for k, v in out.items()}

    def on_event(self, state: State, event: Event, t: int):
        f = np.array(state["f"], copy=True)
        i = np.array(state["i"], copy=True)
        p = event.payload
        names = {n: k for k, n in enumerate(PARAM_NAMES)}
        crit = self.cfg.crit_mask
        if event.kind == "fcs.channel_fault":
            c, sub, on = int(p["channel"]), int(p["subsystem"]), bool(p["active"])
            if not (0 <= c < 4 and 0 <= sub < 23):
                raise ContractError(f"fcs.channel_fault: channel {c} / subsystem {sub} out of range")
            if on:
                i[I_CHFLT + c] |= 1 << sub
            else:
                i[I_CHFLT + c] &= ~(1 << sub)
        elif event.kind == "fcs.actuator_fault":
            s, mode, on = int(p["surface"]), str(p["mode"]), bool(p["active"])
            if not 0 <= s < N_SURF:
                raise ContractError(f"fcs.actuator_fault: surface {s} out of range")
            if mode == "jam":
                i[I_JAM + s] = 1 if on else 0
            elif mode == "servo":
                c = int(p["channel"])
                if not 0 <= c < 4:
                    raise ContractError(f"fcs.actuator_fault: channel {c} out of range")
                if on:
                    i[I_SERVO + s] |= 1 << c
                else:
                    i[I_SERVO + s] &= ~(1 << c)
            else:
                raise ContractError(f"fcs.actuator_fault: unknown mode {mode!r}")
        elif event.kind == "fcs.reset":
            frames = round(self.cfg.p[names["reset_time"]] / self.cfg.tf)
            for c in range(4):
                if (i[I_CHFLT + c] & crit) == 0:
                    st = i[I_CHST + c] & ~(CH_FAILED | CH_DROPOUT | CCDL_FAIL)
                    if st != i[I_CHST + c] or i[I_CBIT + c] != 0:
                        st |= CH_RESET
                        i[I_RSTCNT + c] = max(frames, 1)
                    i[I_CHST + c] = st
                    i[I_CBIT + c] = 0  # re-latched by CBIT if the fault is still present
                    i[I_CBCNT + c] = 0
            i[I_LFAIL : I_LFAIL + N_SIG] = 0
            i[I_MCNT : I_MCNT + 4 * N_SIG] = 0
            i[I_REVLATCH] = 0
            i[I_VANECNT] = 0
            i[I_ADMIS] = 0
            for s in range(N_SURF):
                if i[I_SERVO + s] == 0:
                    i[I_ACTBIT + s] = 0
                    i[I_ACTCNT + s] = 0
        elif event.kind in ("fcs.pbit_start", "fcs.mbit_start", "ops.power_up"):
            # ops.power_up (M02 at the engine start, W2.5 / W2.1a): the DFCC power-up BIT, as fcs.pbit_start
            st_i, tm_i, key = (
                (I_PBIT, I_PBITT, "pbit_time")
                if event.kind in ("fcs.pbit_start", "ops.power_up")
                else (I_MBIT, I_MBITT, "mbit_time")
            )
            if i[I_GROUND] != 1:
                raise ContractError(f"{event.kind} requires weight on wheels")
            i[st_i] = BIT_RUNNING
            i[tm_i] = round(self.cfg.p[names[key]] / self.cfg.tf)
        elif event.kind == "fcs.spin_mode":
            i[I_SPIN] = 1 if bool(p["on"]) else 0
        elif event.kind == "fcs.wow_fault":
            leg, val, on = int(p["leg"]), int(p["value"]), bool(p["active"])
            if not (0 <= leg < 3 and val in (0, 1)):
                raise ContractError(f"fcs.wow_fault: leg {leg} / value {val} out of range")
            if on:
                i[I_WOWF] |= 1 << leg
                i[I_WOWV] = (i[I_WOWV] & ~(1 << leg)) | (val << leg)
            else:
                i[I_WOWF] &= ~(1 << leg)
                i[I_WOWV] &= ~(1 << leg)
        else:
            return super().on_event(state, event, t)
        return {"f": f, "i": i}, []


__all__ = ["Fcs", "FcsIC", "frame_schedule", "ic_params"]
