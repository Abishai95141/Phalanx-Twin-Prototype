"""M04 kernel modules: :class:`PilotModule` (Tejas mode) and :class:`PilotReplay` (proxy mode).

Streams (AD-37), keyed (scenario, tail, sortie) like every per-sortie exogenous input:

| Stream | Use |
|---|---|
| ``pilot.remnant`` | 3 normals per tick (stick pitch, stick roll, throttle remnant), index = absolute tick |
| ``pilot.aar`` | one normal per AAR contact (closure-speed draw), index = contact number in the sortie |

The plan (``scenario.sortie_plan`` event or the constructor) is copied into the state (segment times on
this System's kernel clock, segment tables, per-pilot traits, AAR closures), so snapshots and forks carry it.

**Utility events to M09** (AD-44 catalogue; ``utilities=`` module id; flat payloads, M09 convention),
scheduled from the plan when it is loaded (``scenario.sortie_plan``, or :meth:`PilotModule.initial_events`
for a constructor plan) [A-W1.1-46]:

| Event | When |
|---|---|
| ``util.jfs_start`` {tail} | start of each ENGINE_START segment |
| ``util.jfs_abort`` {tail} | end of that segment if N2 never reached the light-off fraction (hung start;
  checked by the self-event ``pilot.start_check`` against the kernel's ``started`` flag) |
| ``util.chute_deploy`` {tail, emergency=False} | touchdown of the full-stop landing, if the plan streams the
  chute (M02 ``chute``) |
| ``util.chute_jettison`` {tail} | start of the following TAXI_IN segment |
| ``util.store_release`` {tail, station} | end of each dive-delivery pass of a ground-attack or composite
  mission, stations in ``release_stations`` order (one store each) |
| ``util.fire_extinguish`` {tail} | ``fire_reaction`` after a ``pilot.fire_warning`` event (the W2 hook for
  the fire warning: M04 has no catalogued fire-warning input) |

**Segment events to M02** (W2.1a take-off fix, A-W2.1-9; ``segment_target=`` module id): ``pilot.segment``
{tail, segment, fine} at every change of the segment in force (the kernel gates the take-off and landing rolls
on lift-off and touchdown), stamped at the tick of the change; segment = the segment count at the end of the
plan (engine cut-off), fine = POSTFLIGHT. With a segment target the plan-boundary utility events after the
take-off (chute deploy at the full-stop landing roll, chute jettison at the next taxi, store releases at the
end of the dive passes) are emitted at the actual segment changes, not at plan times.

**FCS events to M05** (AD-47; ``fcs=`` module id; flat payloads) [A-W1.1-47]: ``fcs.spin_mode`` {tail, on}
when the kernel's spin flag changes (checked by the self-event ``pilot.monitor`` once a second over the
plan), ``fcs.reset`` {tail} ``reset_reaction`` after a ``pilot.fcs_caution`` event (the W2 hook for the
FCS caution). The toe brakes are the output port ``brake_cmd`` (2,).
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from phalanx.core.events import Event
from phalanx.core.module import ContractError, Inputs, ModuleBase, Outputs, ParamSet
from phalanx.core.rng import StreamDecl, Variate
from phalanx.core.state import Field, State, StateSchema
from phalanx.core.time import RG_240
from phalanx.dictionary.params import load_params
from phalanx.scenario import phases as PH
from phalanx.scenario.config import COMPOSITE, GROUND_ATTACK, P_DIVE, P_TANKER
from phalanx.scenario.pilots import T_AAR_MEAN, T_AAR_SD, T_GAIN, T_REMNANT, T_TAU
from phalanx.scenario.plan import N_SEG_F, N_SEG_I, S_PHASE, S_PRIM, SortiePlan
from phalanx.scenario.replay import ReplayInputs

from . import kernel as K
from .ports import ports, replay_ports

PLAN_EVENT = "scenario.sortie_plan"
SUBSYSTEM = "pilot"
EV_START_CHECK, EV_FIRE_WARNING = "pilot.start_check", "pilot.fire_warning"
EV_MONITOR, EV_FCS_CAUTION = "pilot.monitor", "pilot.fcs_caution"
EV_SEGMENT = "pilot.segment"
MONITOR_NS = 1_000_000_000  # spin-flag check period


@dataclass(frozen=True)
class PilotConfig:
    vector: np.ndarray  # kernel parameter vector (K.P_NAMES order)
    delay_max_s: float
    aar_closure_max: float
    params: ParamSet
    fire_reaction_s: float = 3.0
    release_stations: tuple[int, ...] = (2, 3, 4)
    reset_reaction_s: float = 5.0


def load_pilot_config(platform: str = "tejas") -> PilotConfig:
    """M04.yaml plus the N2 reference speed from the dictionary constants (channel_reference)."""
    from phalanx.dictionary import load_dictionary

    ps = load_params("M04", platform=platform)["guidance"]
    n2_100 = float(load_dictionary(platform=platform).param_set("channel_reference").value("n2_100pct"))
    vals = {k: float(ps.value(k)) for k in K.P_NAMES if k in ps}
    vals["n2_100"] = n2_100
    vals["g0"] = 9.80665
    vec = np.array([vals[k] for k in K.P_NAMES], dtype=np.float64)
    vec.flags.writeable = False
    return PilotConfig(
        vec,
        float(ps.value("delay_max")),
        float(ps.value("aar_closure_max")),
        ps,
        float(ps.value("fire_reaction")),
        tuple(int(x) for x in np.atleast_1d(np.asarray(ps.value("release_stations")))),
        float(ps.value("reset_reaction")),
    )


def aar_closures(
    plan: SortiePlan, stream, period_s: float, closure_max: float
) -> tuple[np.ndarray, np.ndarray]:
    """Per-segment first-contact index and the closure speed (m/s) of every AAR contact of a sortie.

    Contact c ~ N(pilot mean, pilot SD), clipped to (0.05 kt, 10 kt] [A-W1.1-44]; draw index = contact number.
    """
    dur = plan.segment_durations_s()
    off = np.zeros(plan.n_segments, dtype=np.int64)
    n = 0
    for j in range(plan.n_segments):
        off[j] = n
        if int(plan.seg_i[j, S_PRIM]) == P_TANKER:
            n += max(1, math.ceil(dur[j] / period_s))
    z = stream.draws(0, n) if n else np.zeros(0)
    mean, sd = float(plan.pilot_traits[T_AAR_MEAN]), float(plan.pilot_traits[T_AAR_SD])
    lo = 0.05 * 1852.0 / 3600.0
    return off, np.clip(mean + sd * z, lo, closure_max)


class PilotModule(ModuleBase):
    """Deterministic guidance + crossover-type overlay producing inceptors, PLA and discretes (240 Hz)."""

    version = "1.0.0"
    rate = RG_240

    def __init__(
        self,
        id: str,
        cfg: PilotConfig,
        *,
        n_engines: int = 1,
        plan: SortiePlan | None = None,
        t_kernel0_ns: int = 0,
        compiled: bool = True,
        utilities: str | None = None,
        fcs: str | None = None,
        segment_target: str | None = None,
        identity=None,
    ) -> None:
        self.ports_in, self.ports_out, self.bindings = ports(n_engines)
        self.utilities = utilities
        self.fcs = fcs
        self.segment_target = segment_target
        self.emits_events = segment_target is not None
        self.step_block_emits_events = segment_target is not None
        self.cfg = cfg
        self.n_engines = n_engines
        self._plan0 = plan
        self._t0 = int(t_kernel0_ns)
        self._nb = round(cfg.delay_max_s * 240) + 1
        self._kernel = K.pilot_kernel if compiled else K.pilot_kernel_reference
        self.streams = (
            StreamDecl(
                SUBSYSTEM,
                "remnant",
                ("scenario", "tail", "sortie"),
                Variate.NORMAL,
                4096,
                "M04",
                "pilot remnant",
            ),
            StreamDecl(
                SUBSYSTEM, "aar", ("scenario", "tail", "sortie"), Variate.NORMAL, 64, "M04", "AAR closure"
            ),
        )
        self.state_schema = StateSchema(
            "pilot.m04",
            4,
            (
                Field("f", "<f8", (len(K.F_NAMES),)),
                Field("i", "<i8", (len(K.I_NAMES),)),
                Field("buf", "<f8", (3, self._nb)),
                Field("plan_t", "<i8", (None,)),
                Field("plan_f", "<f8", (None, N_SEG_F)),
                Field("plan_i", "<i8", (None, N_SEG_I)),
                Field("aar_off", "<i8", (None,)),
                Field("aar", "<f8", (None,)),
                Field("tail", "<U24", ()),
            ),
        )
        super().__init__(id, cfg.params, identity=identity)

    def _load_plan(self, state: State, plan: SortiePlan | None, t0: int) -> State:
        st = {k: np.array(v, copy=True) for k, v in state.items()}
        if plan is None:
            st["plan_t"] = np.zeros(0, np.int64)
            st["plan_f"] = np.zeros((0, N_SEG_F))
            st["plan_i"] = np.zeros((0, N_SEG_I), np.int64)
            st["aar_off"] = np.zeros(0, np.int64)
            st["aar"] = np.zeros(0)
            st["i"][K.I_NSEG] = 0
            st["i"][K.I_TEND] = 0
            st["i"][K.I_SEGREP] = -1
            st["f"][K.F_GAIN] = 1.0
            st["tail"] = np.array("", dtype="<U24")
            return st
        if self.n_engines != len(plan.engine_serials) and len(plan.engine_serials) != 1:
            raise ContractError("plan engine count does not match n_engines")
        tr = plan.pilot_traits
        st["plan_t"] = (np.asarray(plan.t_off_ns, dtype=np.int64) + t0).astype(np.int64)
        st["plan_f"] = np.array(plan.seg_f, dtype=np.float64)
        st["plan_i"] = np.array(plan.seg_i, dtype=np.int64)
        off, cl = aar_closures(
            plan, self.stream("aar"), float(self.cfg.vector[K.P_AARP]), self.cfg.aar_closure_max
        )
        st["aar_off"], st["aar"] = off, cl
        st["i"][K.I_NSEG] = plan.n_segments
        st["i"][K.I_SEG] = 0
        st["i"][K.I_STARTED] = 0
        st["i"][K.I_SPIN] = 0
        st["i"][K.I_SPINCNT] = 0
        st["i"][K.I_SPINSENT] = 0
        st["i"][K.I_TEND] = t0 + int(plan.t_end_off_ns)
        st["i"][K.I_SHIFT] = 0
        st["i"][K.I_AIRCNT] = 0
        st["i"][K.I_GNDCNT] = 0
        st["i"][K.I_SEGREP] = -1
        st["i"][K.I_CHUTE] = int(bool(plan.chute))
        st["i"][K.I_NDELAY] = min(self._nb - 1, round(float(tr[T_TAU]) * 240))
        st["f"][K.F_GAIN] = float(tr[T_GAIN]) if tr[T_GAIN] > 0 else 1.0
        st["f"][K.F_REMSD] = float(tr[T_REMNANT])
        st["tail"] = np.array(plan.tail, dtype="<U24")
        return st

    # ------------------------------------------------------------------ contract
    def init(self, params, keys) -> State:
        f = np.zeros(len(K.F_NAMES))
        f[K.F_NZC] = 1.0  # the load-factor command starts at 1 g (rate-limited from there, A-W2.1-12)
        st = {
            "f": f,
            "i": np.zeros(len(K.I_NAMES), dtype=np.int64),
            "buf": np.zeros((3, self._nb)),
            "plan_t": np.zeros(0, np.int64),
            "plan_f": np.zeros((0, N_SEG_F)),
            "plan_i": np.zeros((0, N_SEG_I), np.int64),
            "aar_off": np.zeros(0, np.int64),
            "aar": np.zeros(0),
            "tail": np.array("", dtype="<U24"),
        }
        return self._load_plan(st, self._plan0, self._t0)

    def initial_events(self) -> list[Event]:
        """Utility events of a constructor plan (the harness injects them; empty without ``utilities``)."""
        if self._plan0 is None:
            return []
        return self.utility_events(self._plan0, self._t0)

    def utility_events(self, plan: SortiePlan, t0: int) -> list[Event]:
        """The plan's scheduled events on this kernel clock: M09 utility actions (module docstring table) and
        the first spin-flag check (with ``fcs``)."""
        out_fcs = []
        if self.fcs is not None:
            out_fcs.append(Event(t0 + int(plan.t_off_ns[0]), EV_MONITOR, self.id, {}, source=self.id))
        u = self.utilities
        if u is None:
            return out_fcs
        tail = plan.tail
        offs = np.asarray(plan.t_off_ns, dtype=np.int64)
        ends = np.append(offs[1:], int(plan.t_end_off_ns))
        ph = plan.seg_i[:, S_PHASE]
        out: list[Event] = []

        def ev(t_off: int, kind: str, target: str, payload: dict) -> None:
            out.append(Event(t0 + int(t_off), kind, target, payload, source=self.id))

        for j in range(plan.n_segments):
            if ph[j] == PH.ENGINE_START and (j == 0 or ph[j - 1] != PH.ENGINE_START):
                ev(offs[j], "util.jfs_start", u, {"tail": tail})
                ev(ends[j], EV_START_CHECK, self.id, {"seg": j})
        if self.segment_target is not None:  # after the take-off these follow the actual segment changes
            return out_fcs + out
        landings = np.flatnonzero(ph == PH.LANDING)
        if plan.chute and landings.size:
            j = int(landings[-1])
            ev(offs[j], "util.chute_deploy", u, {"tail": tail, "emergency": False})
            taxi = [k for k in range(j + 1, plan.n_segments) if ph[k] == PH.TAXI_IN]
            ev(offs[taxi[0]] if taxi else ends[j], "util.chute_jettison", u, {"tail": tail})
        if plan.mission_type in (GROUND_ATTACK, COMPOSITE):
            dives = [j for j in range(plan.n_segments) if int(plan.seg_i[j, S_PRIM]) == P_DIVE]
            for station, j in zip(self.cfg.release_stations, dives, strict=False):
                ev(ends[j], "util.store_release", u, {"tail": tail, "station": int(station)})
        return out_fcs + out

    def initial_outputs(self, state: State) -> Outputs:
        e = self.n_engines
        pla = float(state["f"][K.F_PLA])
        return {
            "stick_pitch": np.array(0.0),
            "stick_roll": np.array(0.0),
            "pedal": np.array(0.0),
            "pla": np.full(e, pla),
            "gear_cmd": np.array(1, dtype=np.int64),
            "airbrake_cmd": np.array(0, dtype=np.int64),
            "ab_select": np.zeros(e, dtype=np.int64),
            "brake_cmd": np.ones(2),  # parked
            "at_engage": np.array(0, dtype=np.int64),
            "at_n1_cmd": np.zeros(e),
        }

    def step_block(self, state: State, inputs: Inputs, t: np.ndarray, dt: float):
        n = int(t.size)
        e = self.n_engines
        tick0 = int(state["i"][K.I_TICK])
        noise = self.stream("remnant").draws(3 * tick0, 3 * n).reshape(n, 3)

        def a(name, shape):
            return np.ascontiguousarray(inputs[name], dtype=np.float64).reshape(n, *shape)

        f, i, buf, sticks, pla, disc, ab, wb, seg = self._kernel(
            state["f"],
            state["i"],
            state["buf"],
            state["plan_t"],
            state["plan_f"],
            state["plan_i"],
            state["aar_off"],
            state["aar"],
            self.cfg.vector,
            a("alt", ()),
            a("tas", ()),
            a("mach", ()),
            a("vel_ned", (3,)),
            a("quat", (4,)),
            a("omega_body", (3,)),
            a("nz", ()),
            np.ascontiguousarray(inputs["wow"], dtype=np.int64).reshape(n, 3),
            a("n2", (e,)),
            np.asarray(t, dtype=np.int64),
            noise,
            dt,
            e,
            K.PH_GROUND,
        )
        new = dict(state)
        new.update({"f": f, "i": i, "buf": buf})
        out = {
            "stick_pitch": sticks[:, K.O_SP].copy(),
            "stick_roll": sticks[:, K.O_SR].copy(),
            "pedal": sticks[:, K.O_PED].copy(),
            "pla": pla,
            "gear_cmd": disc[:, K.D_GEAR].copy(),
            "airbrake_cmd": disc[:, K.D_BRAKE].copy(),
            "ab_select": ab,
            "brake_cmd": wb,
            "at_engage": np.zeros(n, dtype=np.int64),
            "at_n1_cmd": np.zeros((n, e)),
        }
        if not self.emits_events:
            return new, out
        return new, out, self.segment_events(state, seg, np.asarray(t, dtype=np.int64))

    def step(self, state: State, inputs: Inputs, t: int, dt: float):
        one = {k: np.asarray(v)[None, ...] for k, v in inputs.items()}
        res = self.step_block(state, one, np.array([t], np.int64), dt)
        out = {k: np.array(v[0]) for k, v in res[1].items()}
        if not self.emits_events:
            return res[0], out
        return res[0], out, [ev for _t, ev in res[2]]

    def segment_events(self, state: State, seg: np.ndarray, t: np.ndarray) -> list[tuple[int, Event]]:
        """(t_emit, Event) pairs for the changes of the segment in force over a block: ``pilot.segment`` to
        the segment target, and the plan-boundary utility events after the take-off (module docstring).
        ``state`` is the state before the block (its ``seg_rep`` is the segment in force at the previous
        tick)."""
        if self.segment_target is None:
            return []
        prev = int(state["i"][K.I_SEGREP])
        changes = np.flatnonzero(np.diff(np.concatenate([[prev], np.asarray(seg, dtype=np.int64)])) != 0)
        if not changes.size:
            return []
        tail = str(np.asarray(state["tail"]))
        plan_i = np.asarray(state["plan_i"])
        nseg = int(state["i"][K.I_NSEG])
        ph = plan_i[:, S_PHASE] if nseg else np.zeros(0, np.int64)
        prim = plan_i[:, S_PRIM] if nseg else np.zeros(0, np.int64)
        landings = np.flatnonzero(ph == PH.LANDING)
        last_landing = int(landings[-1]) if landings.size else -1
        dives = [j for j in range(nseg) if int(prim[j]) == P_DIVE]
        chute = bool(int(state["i"][K.I_CHUTE]))
        out: list[tuple[int, Event]] = []
        for j in changes:
            tj = int(t[j])
            new_seg = int(seg[j])
            old_seg = prev if j == 0 else int(seg[j - 1])
            if new_seg < 0:
                continue
            fine = int(ph[new_seg]) if new_seg < nseg else PH.POSTFLIGHT
            pay = {"tail": tail, "segment": new_seg, "fine": fine}
            out.append((tj, Event(tj, EV_SEGMENT, self.segment_target, pay, source=self.id)))
            u = self.utilities
            if u is None:
                continue
            if chute and new_seg == last_landing:
                pay_c = {"tail": tail, "emergency": False}
                out.append((tj, Event(tj, "util.chute_deploy", u, pay_c, source=self.id)))
            if (
                chute
                and 0 <= last_landing < new_seg < nseg
                and int(ph[new_seg]) == PH.TAXI_IN
                and all(int(ph[k]) != PH.TAXI_IN for k in range(last_landing + 1, new_seg))
            ):
                out.append((tj, Event(tj, "util.chute_jettison", u, {"tail": tail}, source=self.id)))
            if old_seg in dives:
                k_dive = dives.index(old_seg)
                if k_dive < len(self.cfg.release_stations):
                    pay_s = {"tail": tail, "station": int(self.cfg.release_stations[k_dive])}
                    out.append((tj, Event(tj, "util.store_release", u, pay_s, source=self.id)))
        return out

    def on_event(self, state: State, event: Event, t: int):
        """``scenario.sortie_plan``: load the plan (segment times placed with the payload's
        ``t_kernel0_ns``)."""
        if event.kind == EV_START_CHECK:  # hung start: N2 never reached the light-off fraction
            if self.utilities is None or int(state["i"][K.I_STARTED]):
                return state, []
            tail = str(np.asarray(state["tail"]))
            return state, [Event(t, "util.jfs_abort", self.utilities, {"tail": tail}, source=self.id)]
        if event.kind == EV_MONITOR:  # spin flag -> fcs.spin_mode; re-arm until the plan ends
            if self.fcs is None:
                return state, []
            out = []
            st = {k: np.array(v, copy=True) for k, v in state.items()}
            spin = int(st["i"][K.I_SPIN])
            if spin != int(st["i"][K.I_SPINSENT]):
                st["i"][K.I_SPINSENT] = spin
                tail = str(np.asarray(st["tail"]))
                out.append(
                    Event(t, "fcs.spin_mode", self.fcs, {"tail": tail, "on": bool(spin)}, source=self.id)
                )
            if t + MONITOR_NS < int(st["i"][K.I_TEND]) + int(st["i"][K.I_SHIFT]):
                out.append(Event(t + MONITOR_NS, EV_MONITOR, self.id, {}, source=self.id))
            return st, out
        if event.kind == EV_FCS_CAUTION:
            if self.fcs is None:
                return state, []
            tail = str(np.asarray(state["tail"]))
            t_act = t + round(self.cfg.reset_reaction_s * 1e9)
            return state, [Event(t_act, "fcs.reset", self.fcs, {"tail": tail}, source=self.id)]
        if event.kind == EV_FIRE_WARNING:
            if self.utilities is None:
                return state, []
            tail = str(np.asarray(state["tail"]))
            t_act = t + round(self.cfg.fire_reaction_s * 1e9)
            return state, [
                Event(t_act, "util.fire_extinguish", self.utilities, {"tail": tail}, source=self.id)
            ]
        if event.kind != PLAN_EVENT:
            return super().on_event(state, event, t)
        plan, t0 = SortiePlan.from_payload(event.payload)
        return self._load_plan(state, plan, t0), self.utility_events(plan, t0)


class PilotReplay(ModuleBase):
    """Proxy mode (architecture §14.3, §6 M04 proxy hooks): recorded PLA per engine and the autothrottle
    engage state / N1 command passed through; sticks neutral; gear down in recorded ground/approach phases."""

    version = "1.0.0"
    rate = RG_240
    state_schema = StateSchema("pilot.replay", 1, (Field("tick", "<i8", ()),))

    def __init__(
        self, id: str, rec: ReplayInputs, *, gear_down_phases: Sequence[int] = (1, 2, 3, 6, 7)
    ) -> None:
        self.ports_in, self.ports_out = replay_ports(rec.n_engines)
        self.rec = rec
        self._gear = np.array(gear_down_phases, dtype=np.int64)
        super().__init__(id, ParamSet("pilot.replay", {}))

    def init(self, params, keys) -> State:
        return {"tick": np.array(0, dtype=np.int64)}

    def _at(self, t: np.ndarray):
        from phalanx.core.time import NS_PER_S, TRUTH_HZ, truth_step_times_ns

        t = np.asarray(t, dtype=np.int64)
        k = -((-t * TRUTH_HZ) // NS_PER_S)
        j = self.rec.index(truth_step_times_ns(k + 1))
        n = t.size
        e = self.rec.n_engines
        return {
            "stick_pitch": np.zeros(n),
            "stick_roll": np.zeros(n),
            "pedal": np.zeros(n),
            "pla": np.ascontiguousarray(self.rec.pla_rad[:, j].T),
            "gear_cmd": np.isin(self.rec.phase[j], self._gear).astype(np.int64),
            "airbrake_cmd": np.zeros(n, dtype=np.int64),
            "ab_select": np.zeros((n, e), dtype=np.int64),
            "brake_cmd": np.zeros((n, 2)),  # not recorded on the proxy
            "at_engage": self.rec.at_engage[j].astype(np.int64),
            "at_n1_cmd": np.ascontiguousarray(self.rec.at_n1_cmd[:, j].T),
        }

    def initial_outputs(self, state: State) -> Outputs:
        out = self._at(np.array([0], dtype=np.int64))
        return {k: np.array(v[0]) for k, v in out.items()}

    def step_block(self, state: State, inputs: Inputs, t: np.ndarray, dt: float):
        return {"tick": np.array(int(state["tick"]) + int(t.size), dtype=np.int64)}, self._at(t)

    def step(self, state: State, inputs: Inputs, t: int, dt: float):
        new, out = self.step_block(state, inputs, np.array([t], np.int64), dt)
        return new, {k: np.array(v[0]) for k, v in out.items()}


__all__ = ["PLAN_EVENT", "PilotConfig", "PilotModule", "PilotReplay", "aar_closures", "load_pilot_config"]
