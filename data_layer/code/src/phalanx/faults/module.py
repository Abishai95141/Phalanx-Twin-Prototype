"""M11 fault injector: schedules faults (stochastic or scripted), applies them as state perturbations through
events, and propagates them through the typed dependency graph (architecture §6 M11, AD-18, AD-27, I6).

Event-only module (``rate = None``). It owns no physics: every effect is an event to the module that owns the
state (``health.fault`` -> M10, ``sensor_fault`` -> M12 with the AD-42 payload, ``monitor.lru_condition`` ->
M14, ``<prefix>.fault`` -> M07/M08/M09/M05/M06). A fault therefore takes the same generation path as healthy
operation; only state values differ (invariant I6, label-leak guard).

**Randomness (AD-37, CRN):** exogenous fault draws are keyed by identity, never by draw order:
- per sortie and mode: ``faults.sortie`` (scenario, tail, sortie), one generator per mode index; a sortie
  flown in two forks gets the same faults, whatever happened before;
- per maintenance job: ``faults.latent`` (scenario, tail, job);
- scripted and triggered faults: ``faults.instance`` (scenario, tail, event = instance number).

Events handled:

- ``faults.sortie_start``: activate due latent defects; draw Poisson / per-event / Markov faults of the sortie
- ``faults.sortie_end``: advance flight hours and latent clocks; clear sortie-scoped intermittents
- ``faults.inject``: scripted fault (an order or a test)
- ``faults.trigger``: M10 damage reached a failure threshold (crack, spall, pump at limit, ...)
- ``faults.maintenance``: a maintenance action may inject a latent defect (per-action probability, latency)
- ``faults.onset`` / ``faults.node`` / ``faults.clear``: internal: apply a fault, realise a cascade node,
  end a fault
- ``faults.sensor_hold``: internal: a bounded sensor drift reached its bound and becomes a bias of the bound
- ``faults.install`` (from M10 on ``cfg.install``): the serial now at an M18 position; active faults located
  there leave with the removed unit (their effects clear; M18 keeps tracking them by serial)

Events sent to M18 (AD-44, hidden truth; ``"maintenance"`` target): ``truth.fault`` at onset,
``truth.fault_clear`` when an instance clears on its own, ``truth.incident``
(:mod:`phalanx.faults.maintenance`). AD-49 start-failure route (``"ops"`` target = M02): the onset of a start
failure (``maintenance.START_FAILURES``) sends ``ops.start_failure`` {tail_no, sortie_id, mode}; M02
ground-aborts the sortie if it has not taken off.
"""

from __future__ import annotations

import fnmatch
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

import numpy as np

from phalanx.core.events import Event
from phalanx.core.module import ContractError, ModuleBase, Outputs, ParamSet
from phalanx.core.rng import StreamDecl, Variate
from phalanx.core.state import Field, State, StateSchema
from phalanx.health.layout import BiasChannel
from phalanx.health.module import serial_value
from phalanx.health.protocol import ceil_second, plain_payload, read_payload

from .catalogue import FaultMode
from .graph import FaultGraph
from .maintenance import INCIDENTS, POSITIONS, START_FAILURES, position_of, symptom_of
from .sensor_faults import PROBE_MODES, SENSOR_FAULT_EVENT, sensor_fault_payload

__all__ = ["PHYSICS_PREFIX", "FaultConfig", "FaultInjector"]

S_PER_H = 3600.0
N_LAT = 16  # latency uniforms carried per fault instance (consumed by the cascade in traversal order)
PHYSICS_PREFIX = {"engine": "eng", "fadec": "fadec", "airframe": "af"}
#: util.fault modes (AD-44, M09) and the mode that ends each when the fault instance clears
UTIL_FAULT_CLEAR = {
    "gen_fail": "gen_restore",
    "bk_fail": "bk_restore",
    "fire_onset": "fire_out",
    "fire_loop_open": "fire_loop_ok",
    "fire_loop_short": "fire_loop_ok",
}
_ID = "<U64"
#: optional fields of a generic (scripted) sensor fault, carried as ``s_<name>`` in its onset
SENSOR_FIELDS = ("rate", "rate_per_s", "duty", "probe", "factor", "level")


@dataclass(frozen=True)
class FaultConfig:
    """Instance configuration.

    targets: effect target -> module id (``health`` -> M10, ``sensors`` -> M12, ``monitoring`` -> M14,
        ``engine``, ...). An unwired target drops its effects (``strict`` raises instead).
    bias_channels: M10's ``health.sensor_bias`` index map (= M12's channels, AD-42): sensor faults may name
        only these channels; their spans scale fault magnitudes.
    realise_physics_edges: usage mode (True) realises ``physics`` graph edges and their nodes as events;
        telemetry mode (False) leaves them to the module dynamics (proposed decision PD-W1.5-1).
    usage_detection_sigma: **PROXY (A-W1.5-26)**: in usage mode, a covered fault with detection codes and no
        explicit monitoring effect shifts the first code's BIT statistic by this many σ, a stand-in for the
        M08/M05/M09 detection physics that does not run in usage mode. Default 8 σ [ASSUMPTION, sweep
        4-12 σ, A-W1.5-26; the same 8.0 as the graph's monitoring effects in configs/tejas/faults/graph.yaml];
        exposed by ``test_faults_module::test_usage_detection_stand_in_only_when_covered``; replaced when W2.1
        runs the controllers' own monitors.
    """

    catalogue: Mapping[str, FaultMode]
    graph: FaultGraph
    targets: Mapping[str, str]
    engine_serials: tuple[str, ...]
    bias_channels: tuple[BiasChannel, ...] = ()
    realise_physics_edges: bool = True
    stochastic: bool = True
    strict: bool = False
    usage_detection_sigma: float = 8.0  # PROXY (A-W1.5-26): usage-mode detection stand-in, 4-12 σ
    tail_no: str = ""  # M18 tail name in truth.* events (default: the run identity's tail)
    mode_ids: tuple[str, ...] = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "mode_ids", tuple(self.catalogue))


class FaultInjector(ModuleBase):
    """M11 (see module docstring). ``params`` is the merged ParamSet of ``configs/tejas/params/M11.yaml``."""

    version = "1.0.0"
    rate = None
    ports_in = ()
    emits_events = False
    streams = (
        StreamDecl(
            "faults",
            "sortie",
            ("scenario", "tail", "sortie"),
            Variate.GENERATOR,
            owner="M11",
            description="per sortie, one generator per mode: counts, onsets, severity, coverage, latency",
        ),
        StreamDecl(
            "faults",
            "latent",
            ("scenario", "tail", "job"),
            Variate.GENERATOR,
            owner="M11",
            description="per maintenance job: latent-defect injection and latency",
        ),
        StreamDecl(
            "faults",
            "instance",
            ("scenario", "tail", "event"),
            Variate.GENERATOR,
            owner="M11",
            description="scripted and triggered faults: severity, coverage, latencies (event = instance)",
        ),
    )
    state_schema = StateSchema(
        "faults.m11",
        5,  # 5: pre_sortie (preflight modes drawn at power-up, W2.5)
        (
            Field("clock", "<i8", (4,)),  # n_sorties, n_instances, n_maint, t_sortie_end
            Field("fh_s", "<f8", ()),
            Field("sortie_id", _ID, ()),
            Field("markov", "<i8", (None,)),
            Field("lat_mode", "<i8", (None,)),
            Field("lat_left_s", "<f8", (None,)),
            Field("lat_job", _ID, (None,)),
            Field("inst_mode", "<i8", (None,)),
            Field("inst_t0", "<i8", (None,)),
            Field("inst_t1", "<i8", (None,)),
            Field("inst_sev", "<f8", (None,)),
            Field("inst_engine", "<i8", (None,)),
            Field("inst_key", _ID, (None,)),
            Field("inst_sortie", _ID, (None,)),
            Field("inst_covered", "<i8", (None,)),
            Field("inst_pos", "<i8", (None,)),
            Field("inst_choice", "<f8", (None,)),  # the instance's choice variate (its "*" picks; W2.1c)
            Field(
                "env_cold", "<i8", ()
            ),  # the current sortie was cold-soaked (graph condition env.cold_soak)
            Field("pos_serial", _ID, (len(POSITIONS),)),
            Field("sortie_open", "<i8", ()),  # 1 between a sortie start and its end (AD-48.2 guard)
            Field("pre_sortie", _ID, ()),  # sortie whose preflight modes were drawn at power-up (W2.5)
        ),
    )

    def __init__(self, id: str, params: ParamSet, *, config: FaultConfig, **kw) -> None:
        super().__init__(id, params, **kw)
        self.config = config
        self._modes = [config.catalogue[m] for m in config.mode_ids]
        self._bias = {b.channel_id: b for b in config.bias_channels}
        numeric = ("delta", "magnitude", "param", "rate_per_s", "rate", "duty", "factor", "level", "probe")
        for m in self._modes:
            for e in m.effects:
                for k in numeric:
                    v = e.fields.get(k)
                    if isinstance(v, str) and v not in params:
                        raise ContractError(f"{m.id}: effect parameter {v!r} missing from M11 params")
            for k in ("rate", "scale", "probability", "p_on", "p_off"):
                v = m.onset.get(k)
                if isinstance(v, str) and v not in params:
                    raise ContractError(f"{m.id}: onset parameter {v!r} missing from M11 params")
            if m.graph_root and m.graph_root not in config.graph.nodes:
                raise ContractError(f"{m.id}: graph root {m.graph_root!r} not in the graph")

    # ------------------------------------------------------------------ state
    def init(self, params: ParamSet, keys) -> State:
        n = len(self._modes)
        z_i = np.zeros(0, np.int64)
        z_f = np.zeros(0, np.float64)
        z_s = np.zeros(0, _ID)
        return {
            "clock": np.array([0, 0, 0, -1], np.int64),
            "fh_s": np.array(0.0),
            "sortie_id": np.array("", _ID),
            "markov": np.zeros(n, np.int64),
            "lat_mode": z_i,
            "lat_left_s": z_f,
            "lat_job": z_s,
            "inst_mode": z_i,
            "inst_t0": z_i,
            "inst_t1": z_i,
            "inst_sev": z_f,
            "inst_engine": z_i,
            "inst_key": z_s,
            "inst_sortie": z_s,
            "inst_covered": z_i,
            "inst_choice": z_f,
            "inst_pos": z_i,
            "env_cold": np.array(0, np.int64),
            "pos_serial": np.full(len(POSITIONS), "", _ID),
            "sortie_open": np.array(0, np.int64),
            "pre_sortie": np.array("", _ID),
        }

    def initial_outputs(self, state: State) -> Outputs:
        return {}  # fault truth leaves M11 only as restricted labels (fault_labels), never as a port

    @staticmethod
    def _copy(state: State) -> dict[str, np.ndarray]:
        return {k: np.array(v, copy=True) for k, v in state.items()}

    def _value(self, v: object) -> float:
        if isinstance(v, str):
            return float(self.params.value(v))
        return float(v)  # type: ignore[arg-type]

    def mode_index(self, mode_id: str) -> int:
        try:
            return self.config.mode_ids.index(mode_id)
        except ValueError:
            raise ContractError(f"unknown fault mode {mode_id!r}") from None

    # ------------------------------------------------------------------ events
    def on_event(self, state: State, event: Event, t: int):
        k = event.kind
        p = event.payload
        if k == "faults.sortie_start":
            return self._sortie_start(state, p, t)
        if k == "faults.sortie_end":
            return self._sortie_end(state, p, t)
        if k == "faults.onset":
            return self._onset(state, p, t)
        if k == "faults.node":
            return state, self._node_effects(state, p, t)
        if k == "faults.clear":
            return self._clear(state, p, t)
        if k == "faults.inject":
            return self._inject(state, p, t)
        if k == "faults.trigger":
            return self._trigger(state, p, t)
        if k == "faults.maintenance":
            return self._maintenance(state, p, t)
        if k == "faults.sensor_hold":
            return state, self._sensor_hold(state, p, t)
        if k == "ops.power_up":  # W2.5: engine start; preflight (start-failure) modes are drawn here
            return self._ops_power_up(state, read_payload(p), t)
        if k == "ops.takeoff":  # AD-48.2: telemetry-mode sortie start at the actual take-off
            return self._ops_takeoff(state, read_payload(p), t)
        if k == "ops.sortie_done":  # AD-48.2: the sortie end (engine cut-off)
            return self._ops_sortie_done(state, read_payload(p), t)
        if k == "faults.install":
            return self._install(state, read_payload(p), t)
        return super().on_event(state, event, t)

    def _severity(self, mode: FaultMode, g: np.random.Generator) -> float:
        s = mode.severity
        d = s.get("dist", "fixed")
        u = float(g.random())
        z = float(g.standard_normal())
        if d == "fixed":
            return float(s.get("value", 1.0))
        if d == "uniform":
            return float(s["lo"]) + u * (float(s["hi"]) - float(s["lo"]))
        if d == "lognormal":
            return float(s.get("median", 1.0)) * float(np.exp(self._value(s["sigma"]) * z))
        raise ContractError(f"{mode.id}: unknown severity distribution {d!r}")

    def _draw_instance(
        self, mode: FaultMode, g: np.random.Generator
    ) -> tuple[float, bool, np.ndarray, float]:
        """(severity, covered, latency uniforms, choice uniform) in a fixed draw order."""
        sev = self._severity(mode, g)
        covered = bool(g.random() < mode.coverage)
        lat = g.random(N_LAT)
        choice = float(g.random())
        return sev, covered, lat, choice

    def _onset_event(
        self,
        t: int,
        mi: int,
        sev: float,
        covered: bool,
        lat: np.ndarray,
        choice: float,
        engine: int = 0,
        key: str = "",
    ) -> Event:
        return Event(
            t,
            "faults.onset",
            self.id,
            {
                "mode": int(mi),
                "severity": float(sev),
                "covered": bool(covered),
                "lat": np.asarray(lat, np.float64),
                "choice": float(choice),
                "engine": int(engine),
                "key": str(key),
            },
            source=self.id,
        )

    def _ops_takeoff(self, state: State, d: Mapping, t: int):
        """``ops.takeoff`` (M02, AD-48.2): the sortie of this tail starts at take-off; onsets are placed over
        the planned airborne window [t_takeoff, t_landing] with the plan's per-sortie drivers (AB lights,
        engine starts, landings, dust exposure), exactly as ``faults.sortie_start`` (W1 hook) would. Another
        tail's take-off is ignored (one M11 per tail)."""
        if str(d["tail_no"]) != self._tail():
            return state, []
        window = (int(d["t_landing"]) - int(d["t_takeoff"])) * 1e-9
        if window < 0.0:
            raise ContractError(f"{self.id}: ops.takeoff lands before it takes off ({d['sortie_id']})")
        start = {
            "sortie_id": str(d["sortie_id"]),
            "duration_s": window,
            "window_s": window,
            "ab_lights": float(d["ab_lights"]),
            "starts": float(d["engine_starts"]),
            "landings": float(d["landings"]),
            "dust": float(d["dust_index"]),
        }
        return self._sortie_start(state, start, t)

    def _ops_power_up(self, state: State, d: Mapping, t: int):
        """``ops.power_up`` (W2.5; catalogued, M02 emission planned for W2.1a): the engine start of this
        tail's sortie. The preflight modes (:data:`~phalanx.faults.maintenance.START_FAILURES`: JFS cold
        start, hung start, hot start) are drawn now, with onsets at the power-up instant, so a start failure
        reaches M02 (``ops.start_failure``) before the take-off and M02 can ground-abort the sortie
        (A-W2.1c-6). Each mode draws from its own generator of the sortie stream (the same one the take-off
        would use), so the outcome is identical whichever event draws it and no other mode's draws move (CRN).
        The sortie start then skips them. Drivers: ``engine_starts`` (default 1) and ``cold_soak`` (1 =
        cold-soaked, default 0); one JFS start per engine start. A repeated power-up of the same sortie is a
        no-op; another tail's is ignored."""
        if str(d["tail_no"]) != self._tail():
            return state, []
        sid = serial_value(str(d["sortie_id"]))
        if str(state["pre_sortie"]) == sid:
            return state, []
        if int(state["sortie_open"]):
            raise ContractError(
                f"{self.id}: power-up of {sid!r} while sortie {str(state['sortie_id'])!r} is open (AD-48.2)"
            )
        st = self._copy(state)
        st["pre_sortie"] = np.array(sid, _ID)
        st["sortie_id"] = np.array(sid, _ID)
        if not self.config.stochastic:
            return st, []
        starts = float(d.get("engine_starts", 1.0))
        cold = float(d.get("cold_soak", 0.0))
        drivers = {"starts": starts, "cold_jfs_starts": starts * (1.0 if cold > 0.0 else 0.0)}
        s = self.stream("sortie", sortie=sid)
        out: list[Event] = []
        st_now: State = st
        for mi, mode in enumerate(self._modes):
            if mode.id not in START_FAILURES or mode.process != "per_event":
                continue
            g = s.generator(mi)
            count = round(drivers.get(str(mode.onset["driver"]), 0.0))
            pr = self._value(mode.onset["probability"])
            n = int(g.binomial(count, pr)) if count > 0 and pr > 0 else 0
            for _ in range(n):
                g.random()  # the onset-time uniform the take-off path draws: same draw sequence (CRN)
                sev, cov, lat, ch = self._draw_instance(mode, g)
                ev = self._onset_event(t, mi, sev, cov, lat, ch)
                pay = dict(ev.payload) | {"cold_soak": cold}
                st_now, evs = self._onset(st_now, pay, t)
                out += evs
        return st_now, out

    def _ops_sortie_done(self, state: State, d: Mapping, t: int):
        """``ops.sortie_done`` (M02, AD-48.2): the sortie of this tail ends; its flight hours advance the
        latent clocks. Another tail's sortie is ignored."""
        if str(d["tail_no"]) != self._tail():
            return state, []
        return self._sortie_end(state, {"flight_time_s": float(d["flight_hours"]) * S_PER_H}, t)

    def _sortie_start(self, state: State, p: Mapping[str, np.ndarray], t: int):
        if int(state["sortie_open"]):
            raise ContractError(
                f"{self.id}: a sortie started while {str(state['sortie_id'])!r} is open: start M11's sorties "
                "through one path (ops.takeoff, or M10's usage-mode faults.sortie_start), not both (AD-48.2)"
            )
        st = self._copy(state)
        st["sortie_open"] = np.array(1, np.int64)
        sid = str(np.asarray(p["sortie_id"]).item())
        dur = float(p["duration_s"])
        # onsets are placed in [t, t + window]; usage mode (summary at landing) uses a zero window
        win = float(p.get("window_s", np.array(dur)))
        st["sortie_id"] = np.array(serial_value(sid), _ID)
        st["env_cold"] = np.array(int(float(p.get("cold_soak", np.array(0.0))) > 0.0), np.int64)
        st["clock"][3] = t + round(dur * 1e9)
        out: list[Event] = []
        # latent defects whose latency has elapsed manifest in this sortie
        due = st["lat_left_s"] <= 0.0
        for j in np.flatnonzero(due):
            mi = int(st["lat_mode"][j])
            g = self.stream("latent", job=str(st["lat_job"][j])).generator(1000 + mi)
            sev, cov, lat, ch = self._draw_instance(self._modes[mi], g)
            out.append(self._onset_event(t + round(float(g.random()) * win * 1e9), mi, sev, cov, lat, ch))
        keep = ~due
        for f in ("lat_mode", "lat_left_s", "lat_job"):
            st[f] = st[f][keep]
        if self.config.stochastic:
            out += self._stochastic(st, p, t, sid, dur, win)
        st["clock"][0] += 1
        return st, out

    def _env(self, mode: FaultMode, p: Mapping[str, np.ndarray]) -> float:
        env = str(mode.onset.get("env", ""))
        return float(p.get(env, np.array(1.0))) if env else 1.0

    def _stochastic(
        self, st: dict[str, np.ndarray], p, t: int, sid: str, dur: float, win: float
    ) -> list[Event]:
        out: list[Event] = []
        s = self.stream("sortie", sortie=serial_value(sid))
        hours = dur / S_PER_H
        drawn_at_power_up = str(st["pre_sortie"]) == serial_value(sid)
        for mi, mode in enumerate(self._modes):
            proc = mode.process
            if proc not in ("poisson", "per_event", "markov"):
                continue
            if drawn_at_power_up and mode.id in START_FAILURES:
                continue  # drawn at the engine start (ops.power_up, W2.5)
            g = s.generator(mi)
            if proc == "poisson":
                lam = self._value(mode.onset["rate"]) * S_PER_H * hours * self._env(mode, p)
                if "scale" in mode.onset:
                    lam *= self._value(mode.onset["scale"])
                n = int(g.poisson(lam)) if lam > 0 else 0
            elif proc == "per_event":
                count = round(float(np.sum(p.get(str(mode.onset["driver"]), np.array(0.0)))))
                pr = self._value(mode.onset["probability"])
                n = int(g.binomial(count, pr)) if count > 0 and pr > 0 else 0
            else:  # markov: per-sortie two-state transition
                was = int(st["markov"][mi])
                u = float(g.random())
                if was:
                    now = 0 if u < self._value(mode.onset["p_off"]) else 1
                else:
                    now = 1 if u < self._value(mode.onset["p_on"]) * self._env(mode, p) else 0
                st["markov"][mi] = now
                n = 1 if now else 0
            for _ in range(n):
                frac = float(g.random())
                sev, cov, lat, ch = self._draw_instance(mode, g)
                out.append(self._onset_event(t + round(frac * win * 1e9), mi, sev, cov, lat, ch))
        return out

    def _sortie_end(self, state: State, p: Mapping[str, np.ndarray], t: int):
        st = self._copy(state)
        st["sortie_open"] = np.array(0, np.int64)
        ft = float(p["flight_time_s"])
        st["fh_s"] = np.array(float(st["fh_s"]) + ft)
        st["lat_left_s"] = st["lat_left_s"] - ft
        out: list[Event] = []
        sid = str(st["sortie_id"])
        # sortie-scoped (Markov intermittent) instances end with the sortie
        for j in np.flatnonzero((st["inst_t1"] < 0) & (st["inst_sortie"] == sid)):
            mode = self._modes[int(st["inst_mode"][j])]
            if mode.process == "markov" or mode.cls == "intermittent":
                out.append(Event(t, "faults.clear", self.id, {"instance": int(j)}, source=self.id))
        return st, out

    def _inject(self, state: State, p: Mapping[str, np.ndarray], t: int):
        mi = self.mode_index(str(np.asarray(p["mode"]).item()))
        mode = self._modes[mi]
        inst = int(state["clock"][1])
        g = self.stream("instance", event=inst).generator(0)
        sev, cov, lat, ch = self._draw_instance(mode, g)
        if "severity" in p:
            sev = float(p["severity"])
        if "covered" in p:
            cov = bool(p["covered"])
        key = str(np.asarray(p.get("key", np.array(""))).item())
        ev = self._onset_event(t, mi, sev, cov, lat, ch, int(p.get("engine", np.array(0))), key)
        if "cold_soak" in p:  # the graph condition env.cold_soak for this instance's cascade
            pay = dict(ev.payload)
            pay["cold_soak"] = float(p["cold_soak"])
            ev = Event(t, ev.kind, ev.target, pay, source=self.id)
        if "sensor_mode" in p:
            pay = dict(ev.payload)
            pay["sensor_mode"] = str(np.asarray(p["sensor_mode"]).item())
            pay["magnitude"] = float(p.get("magnitude", np.array(0.0)))
            for f in SENSOR_FIELDS:  # generic sensor fault: optional rate, duty, probe, factor, level
                if f in p:
                    pay[f"s_{f}"] = float(p[f])
            ev = Event(t, ev.kind, ev.target, pay, source=self.id)
        return self._onset(state, ev.payload, t)

    def _trigger(self, state: State, p: Mapping[str, np.ndarray], t: int):
        key = str(np.asarray(p["trigger"]).item())
        engine = int(p.get("engine", np.array(0)))
        st: State = state
        out: list[Event] = []
        for mi, mode in enumerate(self._modes):
            if mode.process == "triggered" and fnmatch.fnmatchcase(key, str(mode.onset["trigger"])):
                inst = int(st["clock"][1])
                g = self.stream("instance", event=inst).generator(0)
                sev, cov, lat, ch = self._draw_instance(mode, g)
                st, ev = self._onset(st, self._onset_event(t, mi, sev, cov, lat, ch, engine, key).payload, t)
                out += ev
        return st, out

    def _maintenance(self, state: State, p: Mapping[str, np.ndarray], t: int):
        st = self._copy(state)
        job = serial_value(str(np.asarray(p["job"]).item()))
        action = str(np.asarray(p["action"]).item())
        s = self.stream("latent", job=job)
        from phalanx.health.processes import latent_draw

        for mi, mode in enumerate(self._modes):
            if mode.process != "latent" or action not in mode.onset.get("actions", ()):
                continue
            lat = latent_draw(
                s.generator(mi),
                self._value(mode.onset["probability"]),
                self._value("latent_latency_median"),
                self._value("latent_latency_sigma"),
            )
            if lat is None:
                continue
            st["lat_mode"] = np.append(st["lat_mode"], np.int64(mi))
            st["lat_left_s"] = np.append(st["lat_left_s"], lat)
            st["lat_job"] = np.append(st["lat_job"], np.array(job, _ID))
        st["clock"][2] += 1
        return st, []

    # ------------------------------------------------------------------ onset, effects, cascade
    def _onset(self, state: State, p: Mapping[str, np.ndarray], t: int):
        st = self._copy(state)
        mi = int(p["mode"])
        mode = self._modes[mi]
        inst = int(st["clock"][1])
        st["clock"][1] += 1
        sev = float(p["severity"])
        covered = bool(p["covered"])
        engine = int(p.get("engine", np.array(0)))
        key = str(np.asarray(p.get("key", np.array(""))).item())
        sid = str(st["sortie_id"])
        for name, val in (
            ("inst_mode", np.int64(mi)),
            ("inst_t0", np.int64(t)),
            ("inst_t1", np.int64(-1)),
            ("inst_sev", np.float64(sev)),
            ("inst_engine", np.int64(engine)),
            ("inst_covered", np.int64(covered)),
            ("inst_choice", np.float64(float(p.get("choice", np.array(0.5))))),
        ):
            st[name] = np.append(st[name], val)
        if len(key) > 64:
            raise ContractError(f"{self.id}: fault key {key!r} longer than 64 characters")
        st["inst_key"] = np.append(st["inst_key"], np.array(key, _ID))
        st["inst_sortie"] = np.append(st["inst_sortie"], np.array(sid, _ID))
        pos = position_of(mode, key)
        st["inst_pos"] = np.append(st["inst_pos"], np.int64(POSITIONS.index(pos) if pos else -1))
        ctx = {
            "instance": inst,
            "severity": sev,
            "covered": covered,
            "engine": engine,
            "key": key,
            "choice": float(p.get("choice", np.array(0.5))),
            "sensor_mode": str(np.asarray(p["sensor_mode"]).item()) if "sensor_mode" in p else "",
            "magnitude": float(p.get("magnitude", np.array(0.0))),
            "sensor": {f: float(p[f"s_{f}"]) for f in SENSOR_FIELDS if f"s_{f}" in p},
        }
        out = self._effects(mode, mode.effects_fields(), t, ctx)
        out += self._truth_onset(st, inst, mode, covered, engine, pos, t)
        if self._stand_in(mode, covered):
            out += self._emit(
                "monitoring",
                {"code": mode.codes[0], "magnitude": self.config.usage_detection_sigma},
                t,
                ctx,
                mode,
            )
        if mode.duration_s > 0:
            out.append(
                Event(
                    t + round(mode.duration_s * 1e9),
                    "faults.clear",
                    self.id,
                    {"instance": inst},
                    source=self.id,
                )
            )
        if mode.graph_root:
            mechs = ("graph", "physics") if self.config.realise_physics_edges else ("graph",)
            cold = int(st["env_cold"]) or float(p.get("cold_soak", np.array(0.0))) > 0.0
            acts = self.config.graph.propagate(
                mode.graph_root,
                uniforms=list(np.asarray(p["lat"], float)),
                conditions=("env.cold_soak",) if cold else (),
                mechanisms=mechs,
            )
            for a in acts[1:]:  # the root's own perturbation is the mode's effects
                out.append(
                    Event(
                        t + round(a.t_s * 1e9),
                        "faults.node",
                        self.id,
                        {
                            "node": a.node,
                            "instance": inst,
                            "covered": covered,
                            "engine": engine,
                            "severity": sev,
                        },
                        source=self.id,
                    )
                )
        return st, out

    def _node_effects(self, state: State, p: Mapping[str, np.ndarray], t: int) -> list[Event]:
        node = self.config.graph.nodes[str(np.asarray(p["node"]).item())]
        j = int(p["instance"])
        ctx = {
            "instance": j,
            "severity": 1.0,
            "covered": bool(p["covered"]),
            "engine": int(p["engine"]),
            "key": "",
            "choice": float(state["inst_choice"][j]) if j < state["inst_choice"].size else 0.5,
            "sensor_mode": "",
            "magnitude": 0.0,
            "sensor": {},
        }
        out: list[Event] = []
        for e in node.effects:
            fields = {k: v for k, v in e.items() if k != "target"}
            out += self._emit(str(e["target"]), fields, t, ctx, None)
        return out

    def _effects(
        self, mode: FaultMode, effects: Sequence[tuple[str, Mapping[str, object]]], t: int, ctx
    ) -> list[Event]:
        out: list[Event] = []
        for target, fields in effects:
            out += self._emit(target, fields, t, ctx, mode)
        return out

    def _emit(
        self,
        target: str,
        fields: Mapping[str, object],
        t: int,
        ctx,
        mode: FaultMode | None,
        clear: bool = False,
    ) -> list[Event]:
        mid = self.config.targets.get(target)
        if mid is None:
            if self.config.strict:
                raise ContractError(f"{self.id}: effect target {target!r} is not wired")
            return []
        sev = float(ctx["severity"])
        inst = int(ctx["instance"])
        if target == "health":
            if clear:
                return []
            state = str(fields["state"]).replace("{h}", "2" if "hyd2" in str(ctx["key"]) else "1")
            return [
                Event(
                    t,
                    "health.fault",
                    mid,
                    {
                        "state": state,
                        "engine": int(ctx["engine"]),
                        "delta": self._value(fields["delta"]) * sev,
                        "op": "add",
                    },
                    source=self.id,
                )
            ]
        if target == "sensors":
            return self._sensor_events(fields, t, ctx, mid, clear)
        if target == "monitoring":
            code = str(fields["code"])
            if code.endswith("*") and mode is not None:
                pool = [c for c in mode.codes if fnmatch.fnmatchcase(c, code)]
                code = pool[min(len(pool) - 1, int(float(ctx["choice"]) * len(pool)))] if pool else code
            mag = self._value(fields.get("magnitude", 1.0))
            mag = mag * sev if mode is not None else mag
            return [
                Event(
                    t,
                    "monitor.lru_condition",
                    mid,
                    {
                        "code": code,
                        "magnitude": 0.0 if clear else mag,
                        "covered": bool(ctx["covered"]),
                        "instance": inst,
                        "clear": clear,
                    },
                    source=self.id,
                )
            ]
        if target == "fcs":  # AD-47 events to M05 (plain keys, as M05 reads them)
            return self._fcs_events(fields, t, ctx, mid, clear)
        if target == "utilities":  # AD-44 util.fault to M09 (plain keys, as M09 reads them)
            umode = str(fields["mode"])
            if clear:
                umode = UTIL_FAULT_CLEAR.get(umode, "")
                if not umode:
                    return []
            return [Event(t, "util.fault", mid, {"tail": self._tail(), "mode": umode}, source=self.id)]
        prefix = PHYSICS_PREFIX[target]
        pay = {
            "tail": self._tail(),
            "mode": str(fields["mode"]),
            "param": self._value(fields.get("param", 1.0)) * sev,
            "instance": inst,
            "engine": int(ctx["engine"]),
            "clear": clear,
        }
        kind = f"{prefix}.fault_inject"  # AD-48.4 catalogued (M11 -> M07/M08/M06); never M08's fadec.fault
        if target != "airframe":
            return [Event(t, kind, mid, pay, source=self.id)]
        return [Event(t, kind, mid, {**pay, "leg": leg}, source=self.id) for leg in self._legs(fields, ctx)]

    @staticmethod
    def _legs(fields: Mapping[str, object], ctx) -> list[int]:
        """Gear legs of an airframe effect (``af.fault_inject`` ``leg``: 0 nose, 1 left main, 2 right main,
        -1 all): ``legs: [..]`` explicit; ``leg: n``; ``leg: "*"`` a main leg by the instance's choice
        variate; ``leg: key`` the side of the trigger key (``..._l`` / ``_r`` / ``_n``); absent: -1
        (aircraft-level)."""
        if "legs" in fields:
            return [int(x) for x in fields["legs"]]  # type: ignore[union-attr]
        v = fields.get("leg", -1)
        if v == "*":
            return [1 + min(1, int(float(ctx["choice"]) * 2.0))]
        if v == "key":
            key = str(ctx["key"])
            side = {"l": 1, "r": 2, "n": 0}.get(key[-1:]) if key[-2:-1] == "_" else None
            if side is None:
                raise ContractError(f"airframe effect leg 'key' needs a ..._l/_r/_n key, got {ctx['key']!r}")
            return [side]
        return [int(v)]  # type: ignore[call-overload]

    def _fcs_events(self, fields: Mapping[str, object], t: int, ctx, mid: str, clear: bool) -> list[Event]:
        """``fcs.channel_fault`` / ``fcs.actuator_fault`` / ``fcs.wow_fault`` (AD-47): ``active`` is false
        when the instance clears. A ``"*"`` channel or surface is chosen by the instance's choice variate."""
        from phalanx.fcs.layout import SUBSYSTEMS
        from phalanx.fcs.ports import N_SURF

        u = float(ctx["choice"])
        base = {"tail": self._tail(), "active": not clear}
        ev = str(fields["event"])

        def pick(key: str, n: int, salt: int = 1) -> int:
            v = fields.get(key, "*")
            return min(n - 1, int((u * salt % 1.0) * n)) if v == "*" else int(v)  # type: ignore[call-overload]

        if ev == "channel_fault":
            pay = {
                **base,
                "channel": pick("channel", 4),
                "subsystem": SUBSYSTEMS.index(str(fields["subsystem"])),
            }
            return [Event(t, "fcs.channel_fault", mid, pay, source=self.id)]
        if ev == "actuator_fault":
            pay = {**base, "surface": pick("surface", N_SURF), "mode": str(fields["mode"])}
            if pay["mode"] == "servo":
                pay["channel"] = pick("channel", 4, salt=N_SURF)
            return [Event(t, "fcs.actuator_fault", mid, pay, source=self.id)]
        if ev == "wow_fault":
            legs = fields.get("legs", [])
            return [
                Event(
                    t,
                    "fcs.wow_fault",
                    mid,
                    {**base, "leg": int(leg), "value": int(fields["value"])},
                    source=self.id,
                )
                for leg in legs  # type: ignore[union-attr]
            ]
        raise ContractError(f"{self.id}: unknown fcs event {ev!r}")

    def _sensor_events(self, fields: Mapping[str, object], t: int, ctx, mid: str, clear: bool) -> list[Event]:
        """``sensor_fault`` events to M12 with the AD-42 payload (``sensor_faults`` module docstring).

        Catalogue units: ``magnitude`` is a fraction of the channel span (x severity); a drift's
        ``rate_per_s`` a fraction of span per second, bounded by the magnitude (``faults.sensor_hold``);
        ``rate`` 1/s; ``level`` a short reading as a fraction of the range from its bottom; ``factor`` the
        slow-response time-constant multiplier; ``probe`` a harness probe index.
        """
        if str(fields.get("mode", "*")) == "*":  # generic (scripted) fault: mode and fields from the order
            smode = str(ctx["sensor_mode"]) or "bias"
            fields = {**ctx["sensor"], "magnitude": ctx["magnitude"], "channel": fields.get("channel", "*")}
        else:
            smode = str(fields["mode"])
        channel = str(fields.get("channel", "*"))
        if channel == "*":
            channel = str(ctx["key"])
        b = self._bias.get(channel)
        if b is None:
            if self.config.strict:
                raise ContractError(f"{self.id}: sensor channel {channel!r} is not an M12 channel")
            return []
        if clear:
            return [Event(t, SENSOR_FAULT_EVENT, mid, sensor_fault_payload(channel, "clear"), source=self.id)]

        def f(name: str, default: object) -> float:
            return self._value(fields.get(name, default))

        span = b.span_si
        lo, hi = b.rails_si
        amp = f("magnitude", 0.0) * float(ctx["severity"]) * span
        kw: dict[str, float | int] = {}
        hold: tuple[int, float] | None = None
        if smode in ("bias", "spikes"):
            kw["value"] = amp
        if smode == "drift":
            r = self._value(fields.get("rate_per_s", fields.get("rate", 0.0))) * span
            kw["value"] = r
            if amp != 0.0 and r != 0.0:
                hold = (t + round(abs(amp / r) * 1e9), float(np.copysign(abs(amp), r)))
        elif smode in ("spikes", "intermittent"):
            kw["rate"] = f("rate", "sensor_intermittent_rate" if smode == "intermittent" else 0.0)
            if smode == "intermittent":
                kw["duty"] = f("duty", "sensor_intermittent_duty")
        elif smode in ("short", "probe_short"):
            kw["value"] = lo + f("level", 1.0 if smode == "short" else 0.0) * (hi - lo)
        elif smode == "slow":
            kw["value"] = f("factor", "slow_response_factor")
        if smode in PROBE_MODES:
            kw["probe"] = int(f("probe", 0.0))
        try:
            pay = sensor_fault_payload(channel, smode, **kw)  # type: ignore[arg-type]
        except ValueError as e:
            raise ContractError(f"{self.id}: {channel}: {e}") from None
        out = [Event(t, SENSOR_FAULT_EVENT, mid, pay, source=self.id)]
        if hold is not None:
            hp = {"instance": int(ctx["instance"]), "channel": channel, "value": hold[1]}
            out.append(Event(hold[0], "faults.sensor_hold", self.id, hp, source=self.id))
        return out

    def _sensor_hold(self, state: State, p: Mapping[str, np.ndarray], t: int) -> list[Event]:
        j = int(p["instance"])
        mid = self.config.targets.get("sensors")
        if mid is None or j >= state["inst_t1"].size or state["inst_t1"][j] >= 0:
            return []  # unwired, or the fault was cleared before its drift reached the bound
        channel = str(np.asarray(p["channel"]).item())
        pay = sensor_fault_payload(channel, "bias", value=float(p["value"]))
        return [Event(t, SENSOR_FAULT_EVENT, mid, pay, source=self.id)]

    # ------------------------------------------------------------------ AD-44: hidden truth to M18
    def _tail(self) -> str:
        return self.config.tail_no or str(self.keys.identity.as_dict().get("tail", ""))

    def fault_id(self, j: int, mode: FaultMode) -> str:
        """The M18 fault id of instance ``j`` (tail-qualified; the FAULT label subject without the tail)."""
        return f"{self._tail()}:{mode.id}#{j}"

    def _truth_onset(self, st, j: int, mode: FaultMode, covered: bool, engine: int, pos: str, t: int):
        out: list[Event] = []
        tt = ceil_second(t)
        ops = self.config.targets.get("ops")
        if ops is not None and mode.id in START_FAILURES:  # AD-49: the start failed; M02 may still abort
            doc = {"tail_no": self._tail(), "sortie_id": str(st["sortie_id"]), "mode": mode.id}
            out.append(Event(tt, "ops.start_failure", ops, plain_payload(doc), source=self.id))
        m18 = self.config.targets.get("maintenance")
        if m18 is None:
            return out
        if pos:
            serial = str(st["pos_serial"][POSITIONS.index(pos)])
            if not serial and pos == "ENG" and engine < len(self.config.engine_serials):
                serial = self.config.engine_serials[engine]
            doc = {
                "fault_id": self.fault_id(j, mode),
                "tail": self._tail(),
                "pos": pos,
                "serial": serial,
                "mode": mode.id,
                "symptom": symptom_of(mode, covered),
                "grounding": mode.cls != "intermittent",
            }
            out.append(Event(tt, "truth.fault", m18, plain_payload(doc), source=self.id))
        if mode.id in INCIDENTS:
            kind, positions = INCIDENTS[mode.id]
            doc = {"tail": self._tail(), "kind": kind, "positions": list(positions)}
            out.append(Event(tt, "truth.incident", m18, plain_payload(doc), source=self.id))
        return out

    def _install(self, state: State, d: Mapping, t: int):
        """``faults.install``: a new serial at an M18 position; faults there leave with the old unit."""
        st = self._copy(state)
        pos, serial = str(d["pos"]), str(d["serial"])
        if pos not in POSITIONS:
            raise ContractError(f"{self.id}: unknown M18 position {pos!r}")
        k = POSITIONS.index(pos)
        if str(st["pos_serial"][k]) == serial:
            return st, []
        old = str(st["pos_serial"][k])
        st["pos_serial"][k] = serial
        out: list[Event] = []
        if old:
            for j in np.flatnonzero((st["inst_t1"] < 0) & (st["inst_pos"] == k)):
                st, ev = self._clear(st, {"instance": int(j), "removed": True}, t)
                out += ev
        return st, out

    def _stand_in(self, mode, covered: bool) -> bool:
        """PROXY A-W1.5-26: whether a covered instance of ``mode`` carries the usage-mode detection stand-in
        (the first detection code's condition to M14), set at its onset and cleared with it."""
        return bool(
            self.config.realise_physics_edges
            and covered
            and mode.codes
            and not any(e.target == "monitoring" for e in mode.effects)
        )

    def _clear(self, state: State, p: Mapping[str, np.ndarray], t: int):
        st = self._copy(state)
        j = int(p["instance"])
        if j >= st["inst_t1"].size or st["inst_t1"][j] >= 0:
            return st, []
        st["inst_t1"][j] = t
        mode = self._modes[int(st["inst_mode"][j])]
        ctx = {
            "instance": j,
            "severity": float(st["inst_sev"][j]),
            "covered": bool(st["inst_covered"][j]),
            "engine": int(st["inst_engine"][j]),
            "key": str(st["inst_key"][j]),
            "choice": float(st["inst_choice"][j]),  # the onset's: a clear addresses the same channel / leg
            "sensor_mode": "",
            "magnitude": 0.0,
            "sensor": {},
        }
        out: list[Event] = []
        for target, fields in mode.effects_fields():
            if target != "health":
                out += self._emit(target, fields, t, ctx, mode, clear=True)
        if self._stand_in(mode, bool(st["inst_covered"][j])):
            # the usage-mode detection stand-in leaves with its instance (W2.5 B8-CHAIN1: a stand-in left set
            # kept M14 declaring the code after the fault was gone)
            stand_in = {"code": mode.codes[0], "magnitude": 0.0}
            out += self._emit("monitoring", stand_in, t, ctx, mode, clear=True)
        m18 = self.config.targets.get("maintenance")
        if m18 is not None and int(st["inst_pos"][j]) >= 0 and not bool(p.get("removed", False)):
            doc = {"fault_id": self.fault_id(j, mode)}
            out.append(Event(ceil_second(t), "truth.fault_clear", m18, plain_payload(doc), source=self.id))
        return st, out


def merged_params(sets: Mapping[str, ParamSet], name: str = "tejas.M11") -> ParamSet:
    params = {}
    for s in sets.values():
        for k in s:
            if k in params:
                raise ContractError(f"duplicate M11 parameter {k!r}")
            params[k] = s[k]
    return ParamSet(name, params)


def load_fault_params(**kw) -> ParamSet:
    from phalanx.dictionary.params import load_params

    return merged_params(load_params("M11", **kw))
