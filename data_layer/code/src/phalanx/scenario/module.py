"""M02 kernel module: :class:`ScenarioModule` (event-only, ``rate = None``) and the order effects API.

Modes:
- **sortie** (telemetry mode, one aircraft per System): constructed with one :class:`~.plan.SortiePlan`.
  The bootstrap event ``scenario.sortie_start`` (from :meth:`ScenarioModule.initial_events`, injected by the
  harness at the sortie's kernel start) emits ``scenario.sortie_plan`` to the configured consumers and one
  self-targeted ``scenario.phase`` event per segment start, which update the held ``phase`` port. With a
  **segment source** (``segment_source=`` the pilot's module id; W2.1a take-off fix, A-W2.1-9) the phases and
  the lifecycle follow the flown segments instead of the plan clock: the phase port is set by each
  ``pilot.segment`` (the pilot ends the take-off roll at the confirmed lift-off and starts the landing roll at
  the confirmed touchdown), ``ops.takeoff`` is sent at the lift-off (planned landing = lift-off + the planned
  airborne duration) and ``ops.sortie_done`` at the end of the flown plan (engine cut-off), with the realised
  take-off and landing instants.
- **fleet** (usage mode): constructed with a :class:`~.config.FleetScenario`. The bootstrap event
  ``scenario.day`` plans each day (layer 1) at 00:00 UTC, schedules ``scenario.slot`` /
  ``scenario.ground_run``
  self-events at each sortie start, and the next day. A slot event builds the sortie (layers 2-6) with the
  order effects in force at that moment and emits ``scenario.sortie_plan`` (with its usage summary) to the
  consumers (M18, M10, ...). ``phase`` follows ``focus_tail`` if one is set (else UNKNOWN).

Orders (M21 -> M02; architecture §11.1 "assign or reassign sorties and mission types; restrict usage (AB, g)";
§6 M02 "programme changes, tail swaps, usage restrictions"), event kinds targeted at this module, applied at
the next planning action (day plan or slot build; "live orders apply at the next epoch boundary"):

| Kind | Payload | Effect |
|---|---|---|
| ``order.tail_status`` | tail, available (0/1) | grounding / release |
| ``order.usage_restriction`` | tail (or ``*``), no_ab (0/1), g_limit (g; <= 0 clears) | AB and g limits |
| ``order.programme_change`` | squadron, rate_scale | planned-rate multiplier |
| ``order.tail_swap`` | sortie_key, tail | fly a slot with another tail |
| ``order.assign_mission`` | sortie_key, mission_type | force a slot's mission type |

The same effects are available as the pure function :func:`apply_order` for W1.8 (M21) and usage-mode code.

**Operations mode** (fleet mode with ``ops=OpsLink(...)``; AD-44, ``configs/interfaces/w1_events.yaml``,
``src/phalanx/maintenance/README.md`` "Event protocol"): M02 is the scenario side of the M18 protocol.

- ``scenario.day`` (00:00 UTC) sends ``ops.offer_request`` to M18 and ``kpi.plan`` (the day's flying task: the
  programme planned on the whole fleet, in sorties and planned airborne hours) to the record sink; the day is
  planned when ``ops.offer`` arrives, on the offered tails only, with the offered usage restrictions.
- A sortie slot (at its engine-start time) builds the plan and sends ``ops.launch``; a same-time
  ``scenario.launch_commit`` (priority 1, after M18's reply) commits it unless ``ops.launch_denied`` arrived
  (the slot is lost; no spare-aircraft substitution). A committed sortie emits its plan to the consumers and,
  at engine cut-off, ``ops.sortie_done`` (M18) and ``usage.sortie_summary`` (M10). Ground runs send only
  ``usage.sortie_summary``.
- ``ops.restrict`` (RESTRICT_USAGE) applies at the next sortie build (AB -> no AB; G -> g cap; NONE clears;
  expiry ``until_days``); ``ops.assign`` (ASSIGN_SORTIE) sets a tail's sortie count (and mission type) for a
  date, applied when that date is planned.
- A tail grounded by ``order.tail_status`` after launch and before take-off is ground-aborted
  (``ops.ground_abort``); so is a sortie whose engine start failed (``ops.start_failure`` from M11, AD-49)
  before its take-off. A start failure reported at or after take-off is too late to abort: it is counted
  (``n.start_failure_late``) and the sortie flies on. ``m18.disruption`` carries the scenario's
  configured supply disruptions at start.
Payloads use plain top-level keys (AD-48.1, :func:`phalanx.health.protocol.plain_payload`); times sent
to M18 are kernel ns on whole seconds.
"""

from __future__ import annotations

import datetime as dt
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np

from phalanx.core.canonical import canonical_json
from phalanx.core.events import Event
from phalanx.core.module import ContractError, ModuleBase, Outputs
from phalanx.core.state import Field, State, StateSchema
from phalanx.environment.climatology import A_T_STN
from phalanx.environment.config import EnvConfig
from phalanx.health.protocol import plain_payload, read_payload

from . import phases as P
from .config import MISSION_NAMES, FleetScenario, Squadron
from .generator import GROUND_RUN as GROUND_RUN_MISSION
from .generator import GroundRunSpec, Overrides, Planner, Slot, _utc_s, airborne_window_ns, exposure
from .plan import SortiePlan
from .ports import ports
from .refuel import refuel_loads
from .streams import STREAMS

NS = 1_000_000_000
EV_SORTIE_START, EV_PHASE, EV_DAY, EV_SLOT, EV_GROUND_RUN = (
    "scenario.sortie_start",
    "scenario.phase",
    "scenario.day",
    "scenario.slot",
    "scenario.ground_run",
)
PLAN_EVENT = "scenario.sortie_plan"
ORDER_KINDS = (
    "order.tail_status",
    "order.usage_restriction",
    "order.programme_change",
    "order.tail_swap",
    "order.assign_mission",
)
EV_COMMIT, EV_END = "scenario.launch_commit", "scenario.sortie_end"
EV_TAKEOFF = "scenario.takeoff"  # internal: the committed sortie reaches its take-off (AD-48.2)
EV_POWER_UP = "scenario.power_up"  # internal: the committed sortie reaches its engine start (W2.5 / W2.1a)
TAKEOFF = "ops.takeoff"
POWER_UP = "ops.power_up"
#: ``ops.power_up`` payload (W2.5, catalogued; configs/interfaces/w1_events.yaml)
POWER_UP_KEYS = ("tail_no", "sortie_id", "engine_starts", "cold_soak")
#: ``ops.takeoff`` payload (AD-48.2, catalogued; configs/interfaces/w1_events.yaml)
TAKEOFF_KEYS = (
    "sortie_id",
    "tail_no",
    "t_takeoff",
    "t_landing",
    "ab_lights",
    "engine_starts",
    "landings",
    "dust_index",
)
OPS_IN = ("ops.offer", "ops.launch_denied", "ops.assign", "ops.restrict", "ops.start_failure")
I_DAY, I_EMITTED, I_PHASE_FINE, I_PHASE_DICT, I_NOAB_ALL = range(5)
KEY_DTYPE, TAIL_DTYPE = "<U48", "<U24"
MISSION_CODES = {v: k for k, v in MISSION_NAMES.items()}


@dataclass(frozen=True)
class OpsLink:
    """Operations-mode neighbours (module ids): M18 (``ops.*``), M10 (``usage.sortie_summary``; None = not
    sent) and the record sink for ``kpi.plan`` (None = not sent)."""

    m18: str
    health: str | None = None
    kpi: str | None = None


def _s(v) -> str:
    return str(np.asarray(v))


def _whole_s(t_ns: int) -> int:
    """Round up to a whole second (operations-layer event times are whole seconds; A-W1.8-14)."""
    return -(-int(t_ns) // NS) * NS


def read_doc(state: State) -> dict[str, Any]:
    """The operations-mode document (pending sorties, restrictions, assignments, counters)."""
    return json.loads(np.asarray(state["ops_doc"]).tobytes().decode("utf-8"))


def _put_doc(st: dict, doc: Mapping[str, Any]) -> None:
    st["ops_doc"] = np.frombuffer(canonical_json(doc), dtype=np.uint8).copy()


def _ev(
    t: int, kind: str, target: str | None, doc: Mapping[str, Any], src: str, prio: int = 0
) -> list[Event]:
    if target is None:
        return []
    return [Event(int(t), kind, target, plain_payload(doc), priority=prio, source=src)]


def _in_doc(event: Event) -> dict[str, Any]:
    """An inbound operations event as plain values (AD-48.1, :func:`phalanx.health.protocol.read_payload`)."""
    return read_payload(event.payload)


EMPTY_DOC: dict[str, Any] = {
    "assign": {},
    "denied_reasons": {},
    "n": {
        "assign_unknown_mission": 0,
        "assign_unmet": 0,
        "denied": 0,
        "flown": 0,
        "ground_abort": 0,
        "launched": 0,
        "offers": 0,
    },
    "pending": {},
    "restrict": {},
}


def apply_order(
    state: State, kind: str, payload: Mapping, tails: Sequence[str], squadrons: Sequence[str]
) -> State:
    """Pure: the scenario state after one order (see the module docstring table)."""
    st = {k: np.array(v, copy=True) for k, v in state.items()}
    if kind == "order.tail_status":
        st["unavail"][list(tails).index(_s(payload["tail"]))] = (
            0 if int(np.asarray(payload["available"])) else 1
        )
    elif kind == "order.usage_restriction":
        tail = _s(payload["tail"])
        no_ab = int(np.asarray(payload.get("no_ab", 0)))
        g = float(np.asarray(payload.get("g_limit", 0.0)))
        if tail == "*":
            st["i"][I_NOAB_ALL] = no_ab
            st["glim_all"][0] = g
        else:
            k = list(tails).index(tail)
            st["noab"][k] = no_ab
            st["glim"][k] = g
    elif kind == "order.programme_change":
        st["rate_scale"][list(squadrons).index(_s(payload["squadron"]))] = float(
            np.asarray(payload["rate_scale"])
        )
    elif kind == "order.tail_swap":
        key, tail = _s(payload["sortie_key"]), _s(payload["tail"])
        keys = [str(x) for x in st["swap_keys"]]
        vals = [str(x) for x in st["swap_tails"]]
        if key in keys:
            vals[keys.index(key)] = tail
        else:
            keys.append(key)
            vals.append(tail)
        st["swap_keys"] = np.array(keys, dtype=KEY_DTYPE)
        st["swap_tails"] = np.array(vals, dtype=TAIL_DTYPE)
    elif kind == "order.assign_mission":
        key, mt = _s(payload["sortie_key"]), int(np.asarray(payload["mission_type"]))
        keys = [str(x) for x in st["mis_keys"]]
        vals = [int(x) for x in st["mis_types"]]
        if key in keys:
            vals[keys.index(key)] = mt
        else:
            keys.append(key)
            vals.append(mt)
        st["mis_keys"] = np.array(keys, dtype=KEY_DTYPE)
        st["mis_types"] = np.array(vals, dtype=np.int64)
    else:
        raise ContractError(f"unknown order kind {kind!r}")
    return st


def overrides_from_state(
    state: State, tails: Sequence[str], squadrons: Sequence[str], t: int | None = None
) -> Overrides:
    ov = Overrides()
    if "ops_doc" in state:  # RESTRICT_USAGE from M18 (operations mode), unexpired at t
        for tail, r in sorted(read_doc(state)["restrict"].items()):
            if r.get("until") is not None and t is not None and t >= int(r["until"]):
                continue
            if r["limit"] == "AB":
                ov.no_ab.add(tail)
            elif r["limit"] == "G" and r.get("value") is not None:
                ov.g_limit[tail] = float(r["value"])
    for k, t in enumerate(tails):
        if state["unavail"][k]:
            ov.unavailable.add(t)
        if state["noab"][k]:
            ov.no_ab.add(t)
        if state["glim"][k] > 0:
            ov.g_limit[t] = float(state["glim"][k])
    if state["i"][I_NOAB_ALL]:
        ov.no_ab.add("*")
    if state["glim_all"][0] > 0:
        ov.g_limit["*"] = float(state["glim_all"][0])
    for k, sq in enumerate(squadrons):
        if state["rate_scale"][k] != 1.0:
            ov.rate_scale[sq] = float(state["rate_scale"][k])
    ov.tail_swap.update(
        {str(a): str(b) for a, b in zip(state["swap_keys"], state["swap_tails"], strict=True)}
    )
    ov.mission.update({str(a): int(b) for a, b in zip(state["mis_keys"], state["mis_types"], strict=True)})
    return ov


class ScenarioModule(ModuleBase):
    """M02 scenario / fleet calendar / mission generator (event-only; see the module docstring)."""

    version = "1.1.0"
    rate = None
    streams = STREAMS

    def __init__(
        self,
        id: str,
        params,
        env: EnvConfig,
        *,
        fleet: FleetScenario | None = None,
        plan: SortiePlan | None = None,
        epoch_utc_ns: int | None = None,
        plan_targets: Sequence[str] = (),
        focus_tail: str | None = None,
        t_kernel0_ns: int = 0,
        ops: OpsLink | None = None,
        utilities: str | None = None,
        fcs: str | None = None,
        airframe: str | None = None,
        takeoff_targets: Sequence[str] = (),
        done_targets: Sequence[str] = (),
        segment_source: str | None = None,
        power_up_targets: Sequence[str] = (),
        identity=None,
    ) -> None:
        if (fleet is None) == (plan is None):
            raise ContractError("give exactly one of fleet= (usage mode) or plan= (sortie mode)")
        if ops is not None and fleet is None:
            raise ContractError("operations mode (ops=) needs fleet mode")
        _, self.ports_out, _ = ports()
        self.p, self.env, self.fleet, self.plan = params, env, fleet, plan
        self.plan_targets = tuple(plan_targets)
        self.focus_tail = focus_tail
        self.t_kernel0_ns = int(t_kernel0_ns)
        self.ops = ops
        self.utilities = utilities
        self.fcs = fcs
        self.airframe = airframe
        self.segment_source = segment_source  # sortie mode: phases and lifecycle from pilot.segment
        if segment_source is not None and plan is None:
            raise ContractError("a segment source is a sortie-mode option (plan=)")
        self.takeoff_targets = tuple(takeoff_targets)  # ops.takeoff (M10, M11, M14; AD-48.2)
        self.done_targets = tuple(done_targets)  # ops.sortie_done besides M18 (M11, M14; AD-48.2)
        self.power_up_targets = tuple(power_up_targets)  # ops.power_up at engine start (M05, M11, M14)
        if fleet is not None:
            self.tails = fleet.tails()
            self.squadrons = tuple(sq.sid for sq in fleet.squadrons)
            self.epoch_utc_ns = int(epoch_utc_ns if epoch_utc_ns is not None else fleet.epoch_utc_ns)
            self._sq_of_tail = {t: sq for sq in fleet.squadrons for t in sq.tails}
        else:
            self.tails = (plan.tail,)  # type: ignore[union-attr]
            self.squadrons = (plan.squadron,)  # type: ignore[union-attr]
            self.epoch_utc_ns = int(
                epoch_utc_ns if epoch_utc_ns is not None else plan.t_start_utc_ns - self.t_kernel0_ns  # type: ignore[union-attr]
            )
            self._sq_of_tail = {}
        if ops is not None and self.epoch_utc_ns % NS:
            raise ContractError("operations mode needs a whole-second epoch")
        self._dict_map = P.dictionary_map()
        nt, ns = len(self.tails), len(self.squadrons)
        self.state_schema = StateSchema(
            "scenario.m02",
            2,
            (
                Field("i", "<i8", (5,)),
                Field("unavail", "<i8", (nt,)),
                Field("noab", "<i8", (nt,)),
                Field("glim", "<f8", (nt,)),
                Field("glim_all", "<f8", (1,)),
                Field("rate_scale", "<f8", (ns,)),
                Field("swap_keys", KEY_DTYPE, (None,)),
                Field("swap_tails", TAIL_DTYPE, (None,)),
                Field("mis_keys", KEY_DTYPE, (None,)),
                Field("mis_types", "<i8", (None,)),
                Field("ops_doc", "|u1", (None,)),
            ),
        )
        super().__init__(id, params.params, identity=identity)

    # ------------------------------------------------------------------ helpers
    def planner(self, keys=None) -> Planner:
        if self.fleet is None:
            raise ContractError("planner() needs fleet mode")
        return Planner(self.p, self.env, self.fleet, keys or self.keys)

    def kernel_time(self, utc_ns: int) -> int:
        return int(utc_ns) - self.epoch_utc_ns

    def initial_events(self) -> list[Event]:
        """Bootstrap event(s) the harness injects at start (``System.inject``)."""
        if self.plan is not None:
            return [Event(self.t_kernel0_ns, EV_SORTIE_START, self.id, {}, source=self.id)]
        return [Event(0, EV_DAY, self.id, {"day": 0}, source=self.id)]

    def _squadron(self, sid: str) -> Squadron:
        return next(sq for sq in self.fleet.squadrons if sq.sid == sid)  # type: ignore[union-attr]

    def _refuel_events(self, plan: SortiePlan, t: int) -> list[Event]:
        """``util.refuel`` (M09) at the sortie start (AD-49 fill-to-target): the planned fuel load per M09
        tank (:mod:`.refuel`; flat payload ``tail``, ``tank`` index, ``target_kg``, ``t_fuel`` = the station
        temperature, K). M09 applies its own capacity and temperature check."""
        if self.utilities is None:
            return []
        t_fuel = float(plan.ambient[A_T_STN])
        return [
            Event(
                t,
                "util.refuel",
                self.utilities,
                {"tail": plan.tail, "tank": int(k), "target_kg": float(kg), "t_fuel": t_fuel},
                source=self.id,
            )
            for k, kg in refuel_loads(plan, self.p)
        ]

    def _preparation_events(self, plan: SortiePlan, t: int) -> list[Event]:
        """At the sortie (or ground-run) start, AD-47: ``af.ground_elevation`` {tail, h} to M06 (the base
        field elevation; M06 ignores the geoid, so MSL = its ellipsoidal height) and ``fcs.pbit_start`` {tail}
        to M05 (power-up BIT at preparation, weight on wheels). Flat payloads (M05/M06 convention)."""
        out: list[Event] = []
        if self.airframe is not None:
            pay = {"tail": plan.tail, "h": float(plan.field_elev_m)}
            out.append(Event(t, "af.ground_elevation", self.airframe, pay, source=self.id))
        if self.fcs is not None and self.fcs not in self.power_up_targets:
            out.append(Event(t, "fcs.pbit_start", self.fcs, {"tail": plan.tail}, source=self.id))
        return out

    def _power_up(self, plan: SortiePlan) -> dict[str, Any]:
        """``ops.power_up`` document (W2.5): one engine start; ``cold_soak`` = 1 when the station temperature
        of the sortie is at or below ``cold_soak_temperature`` (the -15 degC soak-start anchor; A-W2.1-11)."""
        cold = float(plan.ambient[A_T_STN]) <= float(self.p.cold_soak_k)
        return {"tail_no": plan.tail, "sortie_id": plan.sortie_id, "engine_starts": 1, "cold_soak": int(cold)}

    def _aborted_done(self, rec: Mapping[str, Any], t: int) -> list[Event]:
        """``ops.sortie_done`` (aborted) to ``done_targets`` for a powered-up sortie ground-aborted at ``t``
        (W2.5: M11 and M14 end the sortie they opened at the power-up)."""
        done = {k: rec[k] for k in SORTIE_DONE_KEYS if k != "aborted"}
        done.update({"t_takeoff": int(t), "t_landing": int(t), "flight_hours": 0.0, "landings": 0})
        done.update({"engine_cycles": 0.0, "chute_streamed": 0, "aborted": True})
        return [
            Event(int(t), "ops.sortie_done", tgt, plain_payload(done), source=self.id)
            for tgt in self.done_targets
        ]

    def _plan_events(self, plan: SortiePlan, t: int, t0_kernel: int, *, with_phases: bool) -> list[Event]:
        out = [
            Event(t, PLAN_EVENT, target, plan.to_payload(t0_kernel), source=self.id)
            for target in self.plan_targets
        ]
        out += self._preparation_events(plan, t)
        if plan.mission_type != GROUND_RUN_MISSION:
            out += self._refuel_events(plan, t)
        if with_phases:
            for j in range(plan.n_segments):
                fine = int(plan.seg_i[j, 0])
                if j > 0 and fine == int(plan.seg_i[j - 1, 0]):
                    continue
                out.append(
                    Event(
                        t0_kernel + int(plan.t_off_ns[j]), EV_PHASE, self.id, {"fine": fine}, source=self.id
                    )
                )
            out.append(
                Event(
                    t0_kernel + int(plan.t_end_off_ns),
                    EV_PHASE,
                    self.id,
                    {"fine": P.POSTFLIGHT},
                    source=self.id,
                )
            )
        return out

    # ------------------------------------------------------------------ contract
    def init(self, params, keys) -> State:
        nt, ns = len(self.tails), len(self.squadrons)
        i = np.zeros(5, dtype=np.int64)
        i[I_PHASE_FINE] = P.POSTFLIGHT  # engine off until the sortie (or the focus tail's sortie) starts
        i[I_PHASE_DICT] = self._dict_map[P.POSTFLIGHT]
        st = {
            "i": i,
            "unavail": np.zeros(nt, dtype=np.int64),
            "noab": np.zeros(nt, dtype=np.int64),
            "glim": np.zeros(nt),
            "glim_all": np.zeros(1),
            "rate_scale": np.ones(ns),
            "swap_keys": np.zeros(0, dtype=KEY_DTYPE),
            "swap_tails": np.zeros(0, dtype=TAIL_DTYPE),
            "mis_keys": np.zeros(0, dtype=KEY_DTYPE),
            "mis_types": np.zeros(0, dtype=np.int64),
        }
        _put_doc(st, EMPTY_DOC)
        return st

    def initial_outputs(self, state: State) -> Outputs:
        return {
            "epoch_utc_ns": np.array(self.epoch_utc_ns, dtype=np.int64),
            "phase": np.array(state["i"][I_PHASE_DICT], dtype=np.int64),
        }

    def on_event(self, state: State, event: Event, t: int):
        kind = event.kind
        if kind in ORDER_KINDS:
            st = apply_order(state, kind, event.payload, self.tails, self.squadrons)
            if (
                self.ops is not None
                and kind == "order.tail_status"
                and not int(np.asarray(event.payload["available"]))
            ):
                return self._ground_abort(st, _s(event.payload["tail"]), t)
            return st, []
        if kind == EV_PHASE:
            st = {k: np.array(v, copy=True) for k, v in state.items()}
            fine = int(np.asarray(event.payload["fine"]))
            st["i"][I_PHASE_FINE] = fine
            st["i"][I_PHASE_DICT] = self._dict_map[fine]
            return st, []
        if kind == EV_SORTIE_START:
            if self.plan is None:
                raise ContractError("sortie_start in fleet mode")
            st = {k: np.array(v, copy=True) for k, v in state.items()}
            st["i"][I_EMITTED] += 1
            up: list[Event] = []
            if self.power_up_targets and self.plan.mission_type != GROUND_RUN_MISSION:
                # the engine start just before the telemetry window (AD-46): power-up at the window start
                pay = plain_payload(self._power_up(self.plan))
                up = [Event(t, POWER_UP, tgt, pay, source=self.id) for tgt in self.power_up_targets]
            if self.segment_source is not None:  # phases and lifecycle follow the flown segments
                fine = int(self.plan.seg_i[0, 0])
                st["i"][I_PHASE_FINE] = fine
                st["i"][I_PHASE_DICT] = self._dict_map[fine]
                doc = read_doc(st)
                doc["flown"] = {"t0": int(t), "t_takeoff": None, "t_landing": None}
                _put_doc(st, doc)
                return st, up + self._plan_events(self.plan, t, t, with_phases=False)
            out = self._plan_events(self.plan, t, t, with_phases=True)
            return st, up + out + self._lifecycle_events(self.plan, t)
        if kind == "ops.start_failure" and self.plan is not None:
            return self._sortie_start_failure(state, read_payload(event.payload), t)
        if kind == "pilot.segment" and self.segment_source is not None:
            return self._on_segment(state, read_payload(event.payload), t)
        if kind == EV_DAY:
            return self._on_day(state, event, t)
        if kind in (EV_SLOT, EV_GROUND_RUN):
            return self._on_slot(state, event, t)
        if self.ops is not None:
            if kind == "ops.offer":
                return self._on_offer(state, _in_doc(event), t)
            if kind in OPS_IN or kind in (EV_COMMIT, EV_END, EV_TAKEOFF, EV_POWER_UP):
                return self._on_ops(state, kind, _in_doc(event), t)
        return super().on_event(state, event, t)

    # ------------------------------------------------------------------ fleet mode: days and slots
    def _on_day(self, state: State, event: Event, t: int):
        fleet = self.fleet
        if fleet is None:
            raise ContractError("scenario.day in sortie mode")
        day = int(np.asarray(event.payload["day"]))
        d = fleet.start + dt.timedelta(days=day)
        st = {k: np.array(v, copy=True) for k, v in state.items()}
        st["i"][I_DAY] = day
        pl = self.planner()
        if self.ops is None:
            ov = overrides_from_state(state, self.tails, self.squadrons, t)
            slots, runs = pl.plan_day(d, ov)
            out = self._schedule(pl, d, slots, runs, ov, t)
        else:
            out = self._ops_day(st, pl, d, day, t)
        if day + 1 < fleet.days:
            out.append(Event(t + 86400 * NS, EV_DAY, self.id, {"day": day + 1}, source=self.id))
        return st, out

    def _schedule(self, pl: Planner, d: dt.date, slots, runs, ov: Overrides, t: int) -> list[Event]:
        out: list[Event] = []
        for gr in runs:
            plan = pl.build_ground_run(gr)
            out.append(
                Event(
                    max(t, self.kernel_time(plan.t_start_utc_ns)),
                    EV_GROUND_RUN,
                    self.id,
                    {
                        "tail": gr.tail,
                        "squadron": gr.squadron.sid,
                        "date": d.isoformat(),
                        "t_utc_s": gr.t_start_utc_s,
                    },
                    source=self.id,
                )
            )
        for s in slots:
            plan = pl.build_sortie(s, ov)
            out.append(
                Event(
                    max(t, self.kernel_time(plan.t_start_utc_ns)),
                    EV_SLOT,
                    self.id,
                    _slot_payload(s, d),
                    source=self.id,
                )
            )
        return out

    def _slot_from(self, pay: Mapping, tail: str) -> Slot:
        sq = self._squadron(_s(pay["squadron"]))
        serial = sq.engine_serials[sq.tails.index(tail)] if tail in sq.tails else _s(pay["serial"])
        return Slot(
            _s(pay["key"]),
            sq,
            dt.date.fromisoformat(_s(pay["date"])),
            int(np.asarray(pay["wave"])),
            int(np.asarray(pay["slot"])),
            float(np.asarray(pay["t_utc_s"])),
            bool(np.asarray(pay["night"])),
            bool(np.asarray(pay["surge"])),
            tail,
            serial,
            _s(pay["pilot"]),
        )

    def _on_slot(self, state: State, event: Event, t: int):
        pl = self.planner()
        ov = overrides_from_state(state, self.tails, self.squadrons, t)
        pay = event.payload
        sq = self._squadron(_s(pay["squadron"]))
        d = dt.date.fromisoformat(_s(pay["date"]))
        if event.kind == EV_GROUND_RUN:
            tail = _s(pay["tail"])
            if tail in ov.unavailable:
                return state, []
            serial = sq.engine_serials[sq.tails.index(tail)]
            plan = pl.build_ground_run(GroundRunSpec(tail, serial, sq, d, float(np.asarray(pay["t_utc_s"]))))
        else:
            key = _s(pay["key"])
            tail = ov.tail_swap.get(key, _s(pay["tail"]))
            if tail in ov.unavailable:
                return state, []  # grounded after planning: the slot is lost (cancelled)
            plan = pl.build_sortie(self._slot_from(pay, tail), ov)
        st = {k: np.array(v, copy=True) for k, v in state.items()}
        if self.ops is None:
            st["i"][I_EMITTED] += 1
            return st, self._plan_events(plan, t, t, with_phases=plan.tail == self.focus_tail)
        if t % NS:
            raise ContractError("operations-mode sortie starts must be whole seconds")
        rec = self._usage_record(pl, plan, sq, t)
        if event.kind == EV_GROUND_RUN:  # no M18 launch: usage drivers only, at engine cut-off
            st["i"][I_EMITTED] += 1
            out = self._plan_events(plan, t, t, with_phases=plan.tail == self.focus_tail)
            return st, out + _ev(
                rec["t_end"], "usage.sortie_summary", self.ops.health, _summary(rec), self.id
            )
        doc = read_doc(st)
        rec["state"] = "requested"
        rec["slot"] = {k: _plain(v) for k, v in pay.items()}
        rec["slot"]["tail"] = tail
        doc["pending"][plan.sortie_id] = rec
        doc["n"]["launched"] += 1
        _put_doc(st, doc)
        out = _ev(
            t,
            "ops.launch",
            self.ops.m18,
            {"sortie_id": plan.sortie_id, "tail_no": tail, "reply_to": self.id},
            self.id,
        )
        out += _ev(t, EV_COMMIT, self.id, {"sortie_id": plan.sortie_id}, self.id, prio=1)
        return st, out

    def _usage_record(self, pl: Planner, plan: SortiePlan, sq: Squadron, t0: int) -> dict[str, Any]:
        sm = plan.summary
        if sm is None:
            raise ContractError("plan without a usage summary")
        off_to, off_ldg = airborne_window_ns(plan)
        t_to, t_ldg = t0 + off_to, t0 + off_ldg
        drv = pl.usage_drivers(plan, sq.base)
        phases = [int(x) for x in plan.seg_i[:, 0]]
        k_start = phases.index(P.ENGINE_START) if P.ENGINE_START in phases else 0
        return {
            "sortie_id": plan.sortie_id,
            "tail_no": plan.tail,
            "t_power_up": int(t0) + int(plan.t_off_ns[k_start]),
            "cold_soak": int(self._power_up(plan)["cold_soak"]),
            "engine_serials": list(plan.engine_serials),
            "ground_run": plan.mission_type == GROUND_RUN_MISSION,
            "t0": int(t0),
            "t_takeoff": (t_to // NS) * NS,
            "t_landing": (t_ldg // NS) * NS,
            "t_end": _whole_s(t0 + int(plan.t_end_off_ns)),
            "flight_hours": float(sm.flight_s) / 3600.0,
            "landings": int(sm.landings),
            "engine_cycles": float(sm.tac),
            "engine_starts": int(sm.starts),
            "eot_s": float(sm.eot_s),
            "ab_lights": int(sm.ab_lights),
            "type1": int(sm.type1),
            "type3": int(sm.type3),
            "type4": int(sm.type4),
            "nz_exceed": [int(x) for x in sm.nz_exceed],
            "mission_type": MISSION_NAMES.get(int(plan.mission_type), "GROUND_RUN"),
            "crew_id": plan.pilot_id,
            **{k: (int(v) if k == "chute_streamed" else float(v)) for k, v in drv.items()},
        }

    # ------------------------------------------------------------------ sortie lifecycle (AD-48.2)
    def _sortie_record(self, plan: SortiePlan, t0: int) -> dict[str, Any]:
        """Sortie-mode record of a plan started at kernel ``t0`` (exact times; the ``ops.takeoff`` /
        ``ops.sortie_done`` fields). The values are the plan's (M02's scenario truth), as in operations
        mode."""
        sm = plan.summary
        if sm is None:
            raise ContractError("plan without a usage summary")
        off_to, off_ldg = airborne_window_ns(plan)
        exp_h, dust = exposure(self.p, plan)
        return {
            "sortie_id": plan.sortie_id,
            "tail_no": plan.tail,
            "t_takeoff": t0 + off_to,
            "t_landing": t0 + off_ldg,
            "t_end": t0 + int(plan.t_end_off_ns),
            "flight_hours": float(sm.flight_s) / 3600.0,
            "landings": int(sm.landings),
            "engine_cycles": float(sm.tac),
            "engine_starts": int(sm.starts),
            "ab_lights": int(sm.ab_lights),
            "dust_index": exp_h * dust,
            "chute_streamed": int(plan.chute),
            "mission_type": MISSION_NAMES.get(int(plan.mission_type), "GROUND_RUN"),
            "crew_id": plan.pilot_id,
            "ground_run": plan.mission_type == GROUND_RUN_MISSION,
        }

    def _on_segment(self, state: State, d: Mapping[str, Any], t: int):
        """``pilot.segment`` (segment-source mode): the phase port follows the flown segment; the lift-off
        (leaving the take-off roll) sends ``ops.takeoff``, the end of the flown plan ``ops.sortie_done``."""
        plan = self.plan
        if str(d["tail"]) != plan.tail:  # type: ignore[union-attr]
            return state, []
        st = {k: np.array(v, copy=True) for k, v in state.items()}
        seg, fine = int(d["segment"]), int(d["fine"])
        nseg = plan.n_segments  # type: ignore[union-attr]
        prev = int(st["i"][I_PHASE_FINE])
        st["i"][I_PHASE_FINE] = fine
        st["i"][I_PHASE_DICT] = self._dict_map[fine]
        doc = read_doc(st)
        flown = doc.setdefault("flown", {"t0": 0, "t_takeoff": None, "t_landing": None})
        out: list[Event] = []
        ground_run = plan.mission_type == GROUND_RUN_MISSION  # type: ignore[union-attr]
        rec = None if ground_run else self._sortie_record(plan, int(flown["t0"]))  # type: ignore[arg-type]
        if prev == P.TAKEOFF and fine != P.TAKEOFF and seg < nseg and rec is not None:
            airborne = int(rec["t_landing"]) - int(rec["t_takeoff"])
            flown["t_takeoff"] = int(t)
            rec = {**rec, "t_takeoff": int(t), "t_landing": int(t) + airborne}
            out += [
                Event(t, TAKEOFF, tgt, plain_payload(_takeoff(rec)), source=self.id)
                for tgt in self.takeoff_targets
            ]
        if fine == P.LANDING and prev != P.LANDING:
            flown["t_landing"] = int(t)
        if seg >= nseg and rec is not None:
            t_to = flown["t_takeoff"] if flown["t_takeoff"] is not None else int(rec["t_takeoff"])
            t_ld = flown["t_landing"] if flown["t_landing"] is not None else int(rec["t_landing"])
            rec = {**rec, "t_takeoff": int(t_to), "t_landing": int(t_ld), "t_end": int(t)}
            done = {**{k: rec[k] for k in SORTIE_DONE_KEYS if k != "aborted"}, "aborted": False}
            out += [
                Event(t, "ops.sortie_done", tgt, plain_payload(done), source=self.id)
                for tgt in self.done_targets
            ]
        _put_doc(st, doc)
        return st, out

    def _sortie_start_failure(self, state: State, d: Mapping[str, Any], t: int):
        """Sortie mode with a segment source: ``ops.start_failure`` from M11 (drawn at the power-up,
        A-W2.5-2) before the take-off ground-aborts the sortie: ``ops.sortie_done`` (aborted) to
        ``done_targets`` now (``aborted`` in the document; :meth:`aborted`; nothing of the lifecycle is
        pre-scheduled in this mode). At or after the take-off it is too late to abort (counted, the sortie
        flies on), as in operations mode;
        so is any start failure without a segment source, whose ``ops.takeoff`` / ``ops.sortie_done`` are
        already queued on the plan clock."""
        plan = self.plan
        if str(d["tail_no"]) != plan.tail or str(d["sortie_id"]) != plan.sortie_id:  # type: ignore[union-attr]
            return state, []
        st = {k: np.array(v, copy=True) for k, v in state.items()}
        doc = read_doc(st)
        flown = doc.get("flown") or {}
        if self.segment_source is None or doc.get("aborted") or flown.get("t_takeoff") is not None:
            doc["start_failure_late"] = int(doc.get("start_failure_late", 0)) + 1
            _put_doc(st, doc)
            return st, []
        doc["aborted"] = {"t": int(t), "mode": str(d["mode"])}
        _put_doc(st, doc)
        t0 = int(flown.get("t0", 0)) if flown else 0
        return st, self._aborted_done(self._sortie_record(plan, t0), t)  # type: ignore[arg-type]

    @staticmethod
    def aborted(state: State) -> bool:
        """Sortie mode: the sortie was ground-aborted (a start failure before the take-off)."""
        return bool(read_doc(state).get("aborted"))

    def _lifecycle_events(self, plan: SortiePlan, t0: int) -> list[Event]:
        """Sortie mode (telemetry, AD-48.2): ``ops.takeoff`` at the plan's take-off to ``takeoff_targets``
        and ``ops.sortie_done`` at engine cut-off to ``done_targets``. A ground run never takes off: none."""
        if plan.mission_type == GROUND_RUN_MISSION or not (self.takeoff_targets or self.done_targets):
            return []
        rec = self._sortie_record(plan, t0)
        out = [
            Event(rec["t_takeoff"], TAKEOFF, tgt, plain_payload(_takeoff(rec)), source=self.id)
            for tgt in self.takeoff_targets
        ]
        done = {**{k: rec[k] for k in SORTIE_DONE_KEYS if k != "aborted"}, "aborted": False}
        out += [
            Event(rec["t_end"], "ops.sortie_done", tgt, plain_payload(done), source=self.id)
            for tgt in self.done_targets
        ]
        return out

    # ------------------------------------------------------------------ operations mode (M18 protocol)
    def _ops_day(self, st: dict, pl: Planner, d: dt.date, day: int, t: int) -> list[Event]:
        ops = self.ops
        if ops is None or self.fleet is None:
            raise ContractError("operations mode only")
        out: list[Event] = []
        if day == 0:
            for cls, factor, a, b in self.fleet.disruptions:
                t0 = self.kernel_time(_midnight_utc_ns(a))
                t1 = self.kernel_time(_midnight_utc_ns(b + dt.timedelta(days=1)))
                doc = {"cls": cls, "factor": factor, "t0": max(t, t0), "t1": t1}
                out += _ev(t, "m18.disruption", ops.m18, doc, self.id)
        if not pl.is_flying_day(d):
            return out
        out += _ev(t, "ops.offer_request", ops.m18, {"day": d.isoformat(), "reply_to": self.id}, self.id)
        if ops.kpi is not None:  # the flying task is set on the whole fleet (availability is the outcome)
            ov = overrides_from_state(st, self.tails, self.squadrons, t)
            ov.unavailable.clear()
            slots, _ = pl.plan_day(d, ov)
            task = {
                "t_utc": self.epoch_utc_ns + t,
                "date": d.isoformat(),
                "planned_sorties": len(slots),
                "planned_fh": sum(pl.planned_flight_s(s, ov) for s in slots) / 3600.0,
            }
            out += _ev(t, "kpi.plan", ops.kpi, task, self.id)
        return out

    def _on_offer(self, state: State, d_in: Mapping[str, Any], t: int):
        st = {k: np.array(v, copy=True) for k, v in state.items()}
        d = dt.date.fromisoformat(str(d_in["day"]))
        offered = {str(x) for x in d_in["tails"]} & set(self.tails)
        doc = read_doc(st)
        doc["n"]["offers"] += 1
        restrict = d_in.get("restrict") or {}
        for tn in sorted(offered):  # M18 is authoritative for the offered tails' restrictions
            r = restrict.get(tn)
            if r:
                doc["restrict"][tn] = {"limit": r["limit"], "value": r.get("value"), "until": r.get("until")}
            else:
                doc["restrict"].pop(tn, None)
        _put_doc(st, doc)
        pl = self.planner()
        ov = overrides_from_state(st, self.tails, self.squadrons, t)
        ov.unavailable |= set(self.tails) - offered
        slots, runs = pl.plan_day(d, ov)
        slots = self._apply_assignments(st, pl, d, slots, offered)
        ov = overrides_from_state(st, self.tails, self.squadrons, t)
        ov.unavailable |= set(self.tails) - offered
        return st, self._schedule(pl, d, slots, runs, ov, t)

    def _apply_assignments(self, st: dict, pl: Planner, d: dt.date, slots: list[Slot], offered: set[str]):
        """ASSIGN_SORTIE for date ``d``: the tail flies exactly ``sorties`` sorties (later slots dropped, or
        extra slots in the squadron's waves where the tail is free), with ``mission_type`` if given."""
        doc = read_doc(st)
        suffix = "|" + d.isoformat()
        items = sorted((k, v) for k, v in doc["assign"].items() if k.endswith(suffix))
        if not items:
            return slots
        mis: dict[str, int] = {}
        for k, a in items:
            del doc["assign"][k]
            tail, n = k[: -len(suffix)], int(a["sorties"])
            sq = self._sq_of_tail.get(tail)
            if sq is None or tail not in offered:
                doc["n"]["assign_unmet"] += n
                continue
            mine = sorted((s for s in slots if s.tail == tail), key=lambda s: (s.t_takeoff_utc_s, s.key))
            if len(mine) > n:
                drop = {s.key for s in mine[n:]}
                slots = [s for s in slots if s.key not in drop]
                mine = mine[:n]
            if len(mine) < n:
                busy = {s.wave for s in mine}
                waves = sorted(
                    {(s.t_takeoff_utc_s, s.wave, s.night, s.surge) for s in slots if s.squadron.sid == sq.sid}
                )
                if not waves:
                    surge = self.fleet.is_surge(d)  # type: ignore[union-attr]
                    hours = self.p.surge_wave_hours if surge else self.p.day_wave_hours
                    waves = [(_utc_s(d, h), w, False, surge) for w, h in enumerate(hours)]
                for t_to, w, night, surge in waves:
                    if len(mine) >= n:
                        break
                    if w in busy:
                        continue
                    new = pl.make_slot(
                        sq, d, w, len(sq.tails) + sq.tails.index(tail), t_to, night, surge, tail
                    )
                    slots.append(new)
                    mine.append(new)
                doc["n"]["assign_unmet"] += n - len(mine)
            mt = a.get("mission_type")
            if mt is not None:
                if mt in MISSION_CODES:
                    mis.update({s.key: MISSION_CODES[mt] for s in mine})
                else:
                    doc["n"]["assign_unknown_mission"] += 1
        _put_doc(st, doc)
        if mis:
            keys = [str(x) for x in st["mis_keys"]] + sorted(mis)
            vals = [int(x) for x in st["mis_types"]] + [mis[k] for k in sorted(mis)]
            st["mis_keys"] = np.array(keys, dtype=KEY_DTYPE)
            st["mis_types"] = np.array(vals, dtype=np.int64)
        return sorted(slots, key=lambda s: (s.t_takeoff_utc_s, s.key))

    def _on_ops(self, state: State, kind: str, d_in: Mapping[str, Any], t: int):
        ops = self.ops
        if ops is None:
            raise ContractError("operations mode only")
        st = {k: np.array(v, copy=True) for k, v in state.items()}
        doc = read_doc(st)
        out: list[Event] = []
        if kind == "ops.launch_denied":
            if doc["pending"].pop(str(d_in["sortie_id"]), None) is not None:
                doc["n"]["denied"] += 1
                reason = str(d_in["reason"])
                doc["denied_reasons"][reason] = int(doc["denied_reasons"].get(reason, 0)) + 1
        elif kind == "ops.restrict":
            tn = str(d_in["tail_no"])
            if d_in["limit"] == "NONE":
                doc["restrict"].pop(tn, None)
            else:
                days = d_in.get("until_days")
                doc["restrict"][tn] = {
                    "limit": d_in["limit"],
                    "value": d_in.get("value"),
                    "until": None if days is None else t + round(float(days) * 86400.0) * NS,
                }
        elif kind == "ops.start_failure":  # AD-49: the engine start failed (M11)
            sid, tail = str(d_in["sortie_id"]), str(d_in["tail_no"])
            rec = doc["pending"].get(sid)
            if rec is not None and rec["tail_no"] == tail and t < int(rec["t_takeoff"]):
                del doc["pending"][sid]
                doc["n"]["ground_abort"] += 1
                pay = {"tail_no": tail, "sortie_id": sid}
                out += _ev(_whole_s(t), "ops.ground_abort", ops.m18, pay, self.id)
                if rec.get("powered"):  # W2.5: M11 / M14 opened the sortie at the power-up: close it
                    out += self._aborted_done(rec, t)
            else:  # airborne already, or a sortie M02 no longer holds: too late to abort
                doc["n"]["start_failure_late"] = int(doc["n"].get("start_failure_late", 0)) + 1
        elif kind == "ops.assign":
            key = f"{d_in['tail_no']}|{d_in['date']}"
            doc["assign"][key] = {
                "sorties": int(d_in["sorties"]),
                "mission_type": d_in.get("mission_type"),
                "order_id": d_in["order_id"],
            }
        elif kind == EV_COMMIT:
            rec = doc["pending"].get(str(d_in["sortie_id"]))
            if rec is None or rec["state"] != "requested":
                return state, []
            rec["state"] = "flying"
            st["i"][I_EMITTED] += 1
            consumers = (self.utilities, self.fcs, self.airframe)
            if (
                self.plan_targets
                or any(c is not None for c in consumers)
                or rec["tail_no"] == self.focus_tail
            ):
                ov = overrides_from_state(st, self.tails, self.squadrons, t)
                plan = self.planner().build_sortie(self._slot_from(rec["slot"], rec["tail_no"]), ov)
                out += self._plan_events(plan, t, int(rec["t0"]), with_phases=plan.tail == self.focus_tail)
            if self.power_up_targets:  # W2.5: ops.power_up at the committed sortie's engine start
                sid = {"sortie_id": rec["sortie_id"]}
                out += _ev(max(int(t), int(rec["t_power_up"])), EV_POWER_UP, self.id, sid, self.id)
            if self.takeoff_targets:  # AD-48.2: ops.takeoff when the committed sortie takes off
                sid = {"sortie_id": rec["sortie_id"]}
                out += _ev(int(rec["t_takeoff"]), EV_TAKEOFF, self.id, sid, self.id)
            out += _ev(int(rec["t_end"]), EV_END, self.id, {"sortie_id": rec["sortie_id"]}, self.id)
        elif kind == EV_POWER_UP:
            rec = doc["pending"].get(str(d_in["sortie_id"]))
            if rec is None or rec["state"] != "flying":
                return state, []  # ground-aborted (or never committed) before its engine start
            rec["powered"] = True
            pay = {"tail_no": rec["tail_no"], "sortie_id": rec["sortie_id"], "engine_starts": 1}
            pay["cold_soak"] = int(rec["cold_soak"])
            for tgt in self.power_up_targets:
                out += _ev(t, POWER_UP, tgt, pay, self.id)
        elif kind == EV_TAKEOFF:
            rec = doc["pending"].get(str(d_in["sortie_id"]))
            if rec is None or rec["state"] != "flying":
                return state, []  # ground-aborted (or never committed) before its take-off
            for tgt in self.takeoff_targets:
                out += _ev(t, TAKEOFF, tgt, _takeoff(rec), self.id)
            return state, out
        elif kind == EV_END:
            rec = doc["pending"].get(str(d_in["sortie_id"]))
            if rec is None or rec["state"] != "flying":
                return state, []
            del doc["pending"][rec["sortie_id"]]
            doc["n"]["flown"] += 1
            done = {k: rec[k] for k in SORTIE_DONE_KEYS if k != "aborted"}
            out += _ev(t, "ops.sortie_done", ops.m18, {**done, "aborted": False}, self.id)
            for tgt in self.done_targets:  # AD-48.2: M11 / M14 follow the sortie end
                out += _ev(t, "ops.sortie_done", tgt, {**done, "aborted": False}, self.id)
            out += _ev(t, "usage.sortie_summary", ops.health, _summary(rec), self.id)
        _put_doc(st, doc)
        return st, out

    def _ground_abort(self, st: dict, tail: str, t: int):
        """An order grounded ``tail``: its launched sorties that have not taken off are ground-aborted."""
        doc = read_doc(st)
        out: list[Event] = []
        for sid in sorted(doc["pending"]):
            rec = doc["pending"][sid]
            if rec["tail_no"] == tail and t < int(rec["t_takeoff"]):
                del doc["pending"][sid]
                doc["n"]["ground_abort"] += 1
                out += _ev(
                    _whole_s(t),
                    "ops.ground_abort",
                    self.ops.m18,  # type: ignore[union-attr]
                    {"tail_no": tail, "sortie_id": sid},
                    self.id,
                )
                if rec.get("powered"):  # W2.5: close the sortie M11 / M14 opened at the power-up
                    out += self._aborted_done(rec, t)
        _put_doc(st, doc)
        return st, out


SORTIE_DONE_KEYS = (
    "sortie_id",
    "tail_no",
    "t_takeoff",
    "t_landing",
    "flight_hours",
    "landings",
    "engine_cycles",
    "engine_starts",
    "chute_streamed",
    "mission_type",
    "crew_id",
    "aborted",
)
USAGE_SUMMARY_KEYS = (
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
    # extras (AD-44 requires at least the catalogued keys)
    "engine_serials",
    "ground_run",
    "t_end",
    "eot_s",
    "ab_lights",
    "type1",
    "type3",
    "type4",
    "nz_exceed",
    "chute_streamed",
    "exposure_h",
)


def _summary(rec: Mapping[str, Any]) -> dict[str, Any]:
    return {k: rec[k] for k in USAGE_SUMMARY_KEYS}


def _takeoff(rec: Mapping[str, Any]) -> dict[str, Any]:
    """``ops.takeoff`` document (AD-48.2): identity, the take-off and planned landing instants, and the plan's
    per-sortie drivers the fault process needs at take-off (AB lights, starts, landings, dust exposure)."""
    return {k: rec[k] for k in TAKEOFF_KEYS}


def _plain(v) -> Any:
    a = np.asarray(v)
    return a.item() if a.ndim == 0 else a.tolist()


def _slot_payload(s: Slot, d: dt.date) -> dict[str, Any]:
    return {
        "key": s.key,
        "squadron": s.squadron.sid,
        "date": d.isoformat(),
        "wave": s.wave,
        "slot": s.slot,
        "t_utc_s": s.t_takeoff_utc_s,
        "night": s.night,
        "surge": s.surge,
        "tail": s.tail,
        "serial": s.engine_serial,
        "pilot": s.pilot_id,
    }


def _midnight_utc_ns(d: dt.date) -> int:
    return int(dt.datetime(d.year, d.month, d.day, tzinfo=dt.UTC).timestamp()) * NS


__all__ = [
    "EV_COMMIT",
    "EV_DAY",
    "EV_END",
    "EV_GROUND_RUN",
    "EV_PHASE",
    "EV_SLOT",
    "EV_SORTIE_START",
    "EV_TAKEOFF",
    "ORDER_KINDS",
    "PLAN_EVENT",
    "SORTIE_DONE_KEYS",
    "TAKEOFF",
    "TAKEOFF_KEYS",
    "USAGE_SUMMARY_KEYS",
    "OpsLink",
    "ScenarioModule",
    "apply_order",
    "overrides_from_state",
    "read_doc",
]
