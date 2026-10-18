"""M03 kernel modules: :class:`EnvironmentModule` (truth loop) and :class:`EnvironmentReplay` (proxy mode).

Contract: architecture §5.5 / AD-36 (``ModuleBase``), AD-22 kernel layout (``kernel.env_kernel``),
W1_interfaces.md §2 M03 ports, AD-37 streams:

| Stream (subsystem.component) | Identity | Use |
|---|---|---|
| ``env_turb.gust`` | scenario, tail, sortie | 4 normals per tick (u, v, w, p forming-filter noise) |
| ``env_turb.gust_events`` | scenario, tail, sortie | GENERATOR unit 0: stochastic 1-cosine gust schedule |
| ``env_dist.f<id>`` (aircraft scope) | scenario, tail, sortie | factor instance, d normals per tick |
| ``env_dist.f<id>`` (unit scope) | scenario, tail, serial, sortie | one per engine / hydraulic serial |

Draws are indexed by the absolute tick in the int state (``I_TICK``): turbulence draw ``4 k .. 4 k + 3``;
factor instance of dimension d: initial state ``0 .. d - 1``, tick k ``d (k + 1) .. d (k + 2) - 1``. No index
depends on a decision or on another stream, so forks with different orders share every exogenous draw (I8).
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from phalanx.core.events import Event
from phalanx.core.module import ContractError, Inputs, ModuleBase, Outputs
from phalanx.core.rng import StreamDecl, Variate
from phalanx.core.state import Field, State, StateSchema
from phalanx.core.time import NS_PER_S, RG_240, TRUTH_DT_S

from . import kernel as K
from .atmosphere import NMAX, anchored_offset_profile, geopotential_altitude, moist_state, ussa76_profile
from .climatology import N_AMBIENT, Ambient
from .config import EnvConfig
from .disturbances import SCOPE_AIRCRAFT, DisturbanceBank, bank_init
from .ports import N_HYD, ports, replay_ports
from .turbulence import FT, N_TURB_STATE, TUSTIN_TABLE, shear_speed

PLAN_EVENT = "scenario.sortie_plan"
TURB_SUBSYSTEM, DIST_SUBSYSTEM = "env_turb", "env_dist"


@dataclass(frozen=True)
class Gust:
    """A discrete 1-cosine gust: starts at kernel time ``t0_s``, axis 0/1/2 (body u/v/w), peak ``vm`` m/s,
    ramp length ``d_m`` (full gust spans 2 d)."""

    t0_s: float
    axis: int
    vm: float
    d_m: float


def standard_ambient(cfg: EnvConfig, *, field_elev_m: float = 0.0) -> Ambient:
    """ISA standard day at the field, dry, calm, no turbulence (default when no plan is given)."""
    prof, n = ussa76_profile(cfg.layers, cfg.constants)
    h = geopotential_altitude(field_elev_m, cfg.constants.r0)
    from .atmosphere import profile_tp

    t, p = profile_tp(prof, n, h, cfg.constants.vector())
    return Ambient(0, field_elev_m, field_elev_m, t, p, 1e-6, 0.0, 0.0, 0, 0.0)


def generate_gusts(
    gen: np.random.Generator, rate_per_s: float, duration_s: float, amp_sd: float, length: tuple[float, float]
) -> list[Gust]:
    """Poisson gust encounters over a sortie [ASSUMPTION A-W1.1-12]; at most ``K.NG``."""
    out: list[Gust] = []
    t = 0.0
    while rate_per_s > 0 and len(out) < K.NG:
        t += float(gen.exponential(1.0 / rate_per_s))
        if t >= duration_s:
            break
        out.append(
            Gust(t, int(gen.integers(0, 3)), float(gen.normal(0.0, amp_sd)), float(gen.uniform(*length)))
        )
    return out


def _cat_c_default() -> tuple[int, ...]:
    """Dictionary flight_phase codes of the MIL-F-8785C Category C (terminal) phases: take-off, approach,
    landing, plus the pattern and touch-and-go phases added in dictionary 0.1.2 (they used to fall back to
    APPROACH)."""
    from phalanx.scenario.phases import dictionary_phase_code

    return tuple(
        dictionary_phase_code(n) for n in ("TAKEOFF", "APPROACH", "ROLLOUT", "PATTERN", "TOUCH_AND_GO")
    )


class EnvironmentModule(ModuleBase):
    """Atmosphere, wind, turbulence and AD-32 disturbances at the aircraft (240 Hz, compiled kernel)."""

    version = "1.0.0"
    rate = RG_240

    def __init__(
        self,
        id: str,
        cfg: EnvConfig,
        *,
        n_engines: int = 1,
        engine_serials: Sequence[str] | None = None,
        hyd_units: Sequence[str] = ("HYD1", "HYD2"),
        ambient: Ambient | None = None,
        profile: tuple[np.ndarray, int] | None = None,
        profile_wind: bool = False,
        gusts: Sequence[Gust] = (),
        cat_c_codes: Sequence[int] | None = None,
        compiled: bool = True,
        identity=None,
    ) -> None:
        n_hyd = len(hyd_units)
        self.ports_in, self.ports_out, self.bindings = ports(n_engines, n_hyd)
        serials = (
            tuple(engine_serials)
            if engine_serials is not None
            else tuple(f"E{k + 1}" for k in range(n_engines))
        )
        if len(serials) != n_engines or len(set(serials)) != n_engines:
            raise ContractError("engine_serials must name each engine once")
        if len(set(hyd_units)) != n_hyd:
            raise ContractError("hyd_units must be distinct")
        self.cfg = cfg
        self.n_engines, self.n_hyd = n_engines, n_hyd
        self.engine_serials, self.hyd_units = serials, tuple(hyd_units)
        self.bank = DisturbanceBank(cfg.factors, n_engines, n_hyd, TRUTH_DT_S)
        self._ambient0 = ambient if ambient is not None else standard_ambient(cfg)
        self._profile0 = profile
        self._profile_wind = bool(profile_wind)
        self._gusts0 = tuple(gusts)
        if len(self._gusts0) > K.NG:
            raise ContractError(f"at most {K.NG} discrete gusts")
        self._cat_c = np.array(cat_c_codes if cat_c_codes is not None else _cat_c_default(), dtype=np.int64)
        self._cat_c.flags.writeable = False
        self._kernel = K.env_kernel if compiled else K.env_kernel_reference
        self._consts = cfg.constants.vector()
        tb = cfg.turbulence
        pv = np.array(
            [tb.b_span, tb.z0_cat_c, tb.z0_other, tb.v_min, *[float(x) for x in cfg.magnus]], dtype=np.float64
        )
        assert pv.size == len(K.P_NAMES)
        pv.flags.writeable = False
        self._p = pv
        decls = [
            StreamDecl(TURB_SUBSYSTEM, "gust", ("scenario", "tail", "sortie"), Variate.NORMAL, 4096, "M03"),
            StreamDecl(
                TURB_SUBSYSTEM, "gust_events", ("scenario", "tail", "sortie"), Variate.GENERATOR, 1, "M03"
            ),
        ]
        seen = set()
        for it in self.bank.instances:
            if it.stream in seen:
                continue
            seen.add(it.stream)
            ident = (
                ("scenario", "tail", "sortie")
                if it.factor.scope == SCOPE_AIRCRAFT
                else ("scenario", "tail", "serial", "sortie")
            )
            decls.append(
                StreamDecl(
                    DIST_SUBSYSTEM, it.stream, ident, Variate.NORMAL, 4096, "M03", "AD-32 disturbance factor"
                )
            )
        self.streams = tuple(decls)
        self.state_schema = StateSchema(
            "environment.m03",
            1,
            (
                Field("f", "<f8", (len(K.F_NAMES),)),
                Field("i", "<i8", (len(K.I_NAMES),)),
                Field("prof", "<f8", (6, NMAX)),
                Field("turb", "<f8", (N_TURB_STATE,)),
                Field("gusts", "<f8", (K.NG, K.N_GUST_COLS)),
                Field("dist", "<f8", (self.bank.state_size,)),
                Field("amb", "<f8", (N_AMBIENT,)),
            ),
        )
        super().__init__(id, cfg.params, identity=identity)

    # ------------------------------------------------------------------ helpers
    def _unit_serial(self, it) -> str:
        if it.unit < 0:
            return ""
        return self.engine_serials[it.unit] if it.factor.group == 0 else self.hyd_units[it.unit]

    def _instance_stream(self, it):
        if it.unit < 0:
            return self.stream(it.stream)
        return self.stream(it.stream, serial=self._unit_serial(it))

    def _apply_ambient(self, f, i, prof, amb: Ambient, profile=None):
        c = self.cfg
        tb = c.turbulence
        f = f.copy()
        i = i.copy()
        f[K.F_FIELD] = amb.field_elev_m
        f[K.F_W20M] = amb.wind_speed_mps
        f[K.F_WDN] = -math.cos(amb.wind_from_rad)
        f[K.F_WDE] = -math.sin(amb.wind_from_rad)
        cls = int(amb.turb_class)
        if not 0 <= cls <= 3:
            raise ContractError(f"turbulence class {cls} not in 0..3")
        f[K.F_SIGHI] = tb.sigma_hi[cls]
        f[K.F_W20T] = tb.w20[cls]
        f[K.F_LHI] = tb.l_hi
        i[K.I_MODEL] = tb.model
        if profile is not None:
            prof, n = profile
            i[K.I_PWIND] = int(self._profile_wind)
            i[K.I_LOCKED] = 1
        elif i[K.I_LOCKED] == 0:
            h_stn = geopotential_altitude(amb.station_height_m, c.constants.r0)
            prof, n = anchored_offset_profile(
                c.layers,
                c.constants,
                h_station=h_stn,
                p_station=amb.p_station_pa,
                t_station=amb.t_station_k,
                e_station=max(amb.e_station_pa, 1e-6),
                vapour_scale_height=c.vapour_scale_height,
            )
            i[K.I_PWIND] = 0
        else:
            n = int(i[K.I_NPROF])
        i[K.I_NPROF] = n
        return f, i, np.array(prof, dtype=np.float64)

    @staticmethod
    def _gust_table(gusts: Sequence[Gust]) -> np.ndarray:
        g = np.zeros((K.NG, K.N_GUST_COLS))
        for k, gu in enumerate(gusts):
            g[k, K.G_T0] = gu.t0_s
            g[k, K.G_AXIS] = gu.axis
            g[k, K.G_VM] = gu.vm
            g[k, K.G_D] = gu.d_m
        return g

    # ------------------------------------------------------------------ contract
    def init(self, params, keys) -> State:
        f = np.zeros(len(K.F_NAMES))
        i = np.zeros(len(K.I_NAMES), dtype=np.int64)
        f, i, prof = self._apply_ambient(f, i, np.zeros((6, NMAX)), self._ambient0, self._profile0)
        b = self.bank
        eps0 = np.zeros(b.state_size)
        for k, it in enumerate(b.instances):
            d = int(b.dims[k])
            o = int(b.offsets[k])
            eps0[o : o + d] = self._instance_stream(it).draws(0, d)
        dist = np.zeros(b.state_size)
        bank_init(dist, b.dims, b.offsets, b.linit, eps0)
        return {
            "f": f,
            "i": i,
            "prof": prof,
            "turb": np.zeros(N_TURB_STATE),
            "gusts": self._gust_table(self._gusts0),
            "dist": dist,
            "amb": self._ambient0.vector(),
        }

    def initial_outputs(self, state: State) -> Outputs:
        f, i = state["f"], state["i"]
        z = float(f[K.F_FIELD])
        t, p, rho, a, q, _wn, _we = moist_state(
            state["prof"], int(i[K.I_NPROF]), z, self._consts, np.asarray(self._p[4:7])
        )
        if i[K.I_PWIND] == 1:
            wn, we = float(_wn), float(_we)
            hp = geopotential_altitude(z + 1000.0 * FT, self.cfg.constants.r0)
            from .atmosphere import PR_WE, PR_WN, _lin

            s = shear_speed(0.0, 1.0, self._p[K.P_Z0O]) / shear_speed(1000.0 * FT, 1.0, self._p[K.P_Z0O])
            wn = _lin(state["prof"], PR_WN, int(i[K.I_NPROF]), hp) * s
            we = _lin(state["prof"], PR_WE, int(i[K.I_NPROF]), hp) * s
        else:
            sp = shear_speed(0.0, f[K.F_W20M], self._p[K.P_Z0O])
            wn, we = sp * f[K.F_WDN], sp * f[K.F_WDE]
        b = self.bank
        y = np.zeros(b.n_out)
        for k in range(len(b.instances)):
            d, o = int(b.dims[k]), int(b.offsets[k])
            yk = float(b.cvec[k, :d] @ state["dist"][o : o + d])
            y += b.gain[k] * yk
        w_eng, w_bleed, w_hyd = b.split(y)
        return {
            "t_s": np.array(t),
            "p_s": np.array(p),
            "rho": np.array(rho),
            "a_sound": np.array(a),
            "q_spec": np.array(q),
            "wind_ned": np.array([wn, we, 0.0]),
            "turb_vel_body": np.zeros(3),
            "turb_rate_body": np.zeros(3),
            "w_engine": np.ascontiguousarray(w_eng),
            "w_bleed_pto": np.ascontiguousarray(w_bleed),
            "w_hyd": np.ascontiguousarray(w_hyd),
        }

    def _noise(self, tick0: int, n: int) -> tuple[np.ndarray, np.ndarray]:
        turb = self.stream("gust").draws(4 * tick0, 4 * n).reshape(n, 4)
        b = self.bank
        dn = np.zeros((n, b.state_size))
        for k, it in enumerate(b.instances):
            d, o = int(b.dims[k]), int(b.offsets[k])
            dn[:, o : o + d] = self._instance_stream(it).draws(d * (tick0 + 1), d * n).reshape(n, d)
        return turb, dn

    def step_block(self, state: State, inputs: Inputs, t: np.ndarray, dt: float):
        n = int(t.size)
        tick0 = int(state["i"][K.I_TICK])
        turb_noise, dist_noise = self._noise(tick0, n)
        alt = np.ascontiguousarray(inputs["alt"], dtype=np.float64).reshape(n)
        hag = np.ascontiguousarray(inputs["hag"], dtype=np.float64).reshape(n)
        tas = np.ascontiguousarray(inputs["tas"], dtype=np.float64).reshape(n)
        phase = np.ascontiguousarray(inputs["phase"], dtype=np.int64).reshape(n)
        t_s = np.asarray(t, dtype=np.int64) / NS_PER_S
        b = self.bank
        f, i, turb, gusts, dist, atm, wind, tvel, trate, wout = self._kernel(
            state["f"],
            state["i"],
            state["prof"],
            state["turb"],
            state["gusts"],
            state["dist"],
            self._p,
            self._consts,
            TUSTIN_TABLE,
            self._cat_c,
            b.dims,
            b.offsets,
            b.phi,
            b.lq,
            b.cvec,
            b.gain,
            alt,
            hag,
            tas,
            phase,
            t_s,
            turb_noise,
            dist_noise,
            dt,
        )
        w_eng, w_bleed, w_hyd = b.split(wout)
        new = {
            "f": f,
            "i": i,
            "prof": state["prof"],
            "turb": turb,
            "gusts": gusts,
            "dist": dist,
            "amb": state["amb"],
        }
        outs = {
            "t_s": atm[:, K.O_T].copy(),
            "p_s": atm[:, K.O_P].copy(),
            "rho": atm[:, K.O_RHO].copy(),
            "a_sound": atm[:, K.O_A].copy(),
            "q_spec": atm[:, K.O_Q].copy(),
            "wind_ned": wind,
            "turb_vel_body": tvel,
            "turb_rate_body": trate,
            "w_engine": np.ascontiguousarray(w_eng),
            "w_bleed_pto": np.ascontiguousarray(w_bleed),
            "w_hyd": np.ascontiguousarray(w_hyd),
        }
        return new, outs

    def step(self, state: State, inputs: Inputs, t: int, dt: float):
        one = {k: np.asarray(v)[None, ...] for k, v in inputs.items()}
        new, out = self.step_block(state, one, np.array([t], np.int64), dt)
        return new, {k: np.array(v[0]) for k, v in out.items()}

    def on_event(self, state: State, event: Event, t: int):
        """``scenario.sortie_plan``: take the plan's ambient (payload ``ambient``, N_AMBIENT floats) and, if
        stochastic gusts are enabled, schedule them over ``duration_s`` from the plan start."""
        if event.kind != PLAN_EVENT:
            return super().on_event(state, event, t)
        amb = Ambient.from_vector(np.asarray(event.payload["ambient"], dtype=np.float64))
        f, i, prof = self._apply_ambient(state["f"], state["i"], state["prof"], amb)
        gusts = state["gusts"]
        tb = self.cfg.turbulence
        if tb.gust_rate > 0 and "duration_s" in event.payload:
            gen = self.stream("gust_events").generator(0)
            t0 = t / NS_PER_S
            g = generate_gusts(
                gen, tb.gust_rate, float(event.payload["duration_s"]), tb.gust_amp_sd, tb.gust_length
            )
            gusts = self._gust_table([Gust(gu.t0_s + t0, gu.axis, gu.vm, gu.d_m) for gu in g])
        new = dict(state)
        new.update({"f": f, "i": i, "prof": prof, "gusts": np.array(gusts), "amb": amb.vector()})
        return new, []


class EnvironmentReplay(ModuleBase):
    """Proxy mode (architecture §14.3): env outputs from a recorded flight condition plus the same AD-32
    disturbance bank and streams as the truth module.

    Record: per-sample pressure altitude (m), Mach and total air temperature (K) at ``rate_hz`` from
    ``t0_ns``; held (zero-order) to the truth frame. Static pressure is ISA at the pressure altitude, static
    temperature T = TAT / (1 + (gamma - 1)/2 M^2) (unit recovery factor [ASSUMPTION A-W1.1-14]); air is dry;
    winds and turbulence are zero (already inside the recorded flight condition).
    """

    version = "1.0.0"
    rate = RG_240

    def __init__(
        self,
        id: str,
        cfg: EnvConfig,
        *,
        pressure_alt_m: np.ndarray,
        mach: np.ndarray,
        tat_k: np.ndarray,
        rate_hz: float,
        t0_ns: int = 0,
        n_engines: int = 1,
        engine_serials: Sequence[str] | None = None,
        hyd_units: Sequence[str] = ("HYD1", "HYD2"),
        identity=None,
    ) -> None:
        inner = EnvironmentModule(
            f"{id}_inner",
            cfg,
            n_engines=n_engines,
            engine_serials=engine_serials,
            hyd_units=hyd_units,
            cat_c_codes=(),
        )
        self._inner = inner
        self.ports_in, self.ports_out = replay_ports(n_engines, len(hyd_units))
        self.streams = inner.streams
        self.state_schema = inner.state_schema
        self.bank = inner.bank
        self.cfg = cfg
        alt = np.asarray(pressure_alt_m, dtype=np.float64)
        if not (alt.shape == np.shape(mach) == np.shape(tat_k)) or alt.ndim != 1 or alt.size < 1:
            raise ContractError("replay arrays must be 1-D and equal length")
        self._rec = (alt.copy(), np.asarray(mach, float).copy(), np.asarray(tat_k, float).copy())
        for a in self._rec:
            a.flags.writeable = False
        self._rate, self._t0 = float(rate_hz), int(t0_ns)
        std, ns = ussa76_profile(cfg.layers, cfg.constants)
        self._std = (std, ns)
        super().__init__(id, cfg.params, identity=identity)

    def bind(self, keys) -> None:
        super().bind(keys)
        self._inner.bind(keys)

    def init(self, params, keys) -> State:
        return self._inner.init(params, keys)

    def _condition(self, t: np.ndarray):
        idx = np.floor((np.asarray(t, np.int64) - self._t0) * self._rate / NS_PER_S).astype(np.int64)
        idx = np.clip(idx, 0, self._rec[0].size - 1)
        return self._rec[0][idx], self._rec[1][idx], self._rec[2][idx]

    def _atm(self, alt, mach, tat):
        c = self.cfg.constants
        std, ns = self._std
        from .atmosphere import profile_tp

        g = c.gamma
        r_d = c.r_star / c.m0
        n = alt.size
        out = np.empty((n, 5))
        cv = c.vector()
        for k in range(n):
            h = geopotential_altitude(float(alt[k]), c.r0)
            _t_isa, p = profile_tp(std, ns, h, cv)
            ts = float(tat[k]) / (1.0 + 0.5 * (g - 1.0) * float(mach[k]) ** 2)
            out[k] = (ts, p, p / (r_d * ts), math.sqrt(g * r_d * ts), 0.0)
        return out

    def initial_outputs(self, state: State) -> Outputs:
        out = self._inner.initial_outputs(state)
        atm = self._atm(*self._condition(np.array([self._t0])))
        for col, name in enumerate(("t_s", "p_s", "rho", "a_sound", "q_spec")):
            out[name] = np.array(atm[0, col])
        out["wind_ned"] = np.zeros(3)
        return out

    def step_block(self, state: State, inputs: Inputs, t: np.ndarray, dt: float):
        n = int(t.size)
        alt, mach, tat = self._condition(t)
        fake = {
            "alt": alt,
            "hag": np.maximum(alt, 0.0),
            "tas": np.full(n, 100.0),
            "phase": np.zeros(n, np.int64),
        }
        new, outs = self._inner.step_block(state, fake, t, dt)
        atm = self._atm(alt, mach, tat)
        for col, name in enumerate(("t_s", "p_s", "rho", "a_sound", "q_spec")):
            outs[name] = atm[:, col].copy()
        outs["wind_ned"] = np.zeros((n, 3))
        outs["turb_vel_body"] = np.zeros((n, 3))
        outs["turb_rate_body"] = np.zeros((n, 3))
        return new, outs

    def step(self, state: State, inputs: Inputs, t: int, dt: float):
        new, out = self.step_block(state, {}, np.array([t], np.int64), dt)
        return new, {k: np.array(v[0]) for k, v in out.items()}


__all__ = [
    "N_HYD",
    "PLAN_EVENT",
    "EnvironmentModule",
    "EnvironmentReplay",
    "Gust",
    "generate_gusts",
    "standard_ambient",
]
