"""M10 health module: the hidden-state catalogue per serial, advanced per sortie by usage, perturbed by faults
and reset by maintenance (architecture §6 M10, §5.2, §9; W1_interfaces.md "M10 Health").

Event-only module (``rate = None``). Its held outputs are the four ``health.*`` ports. Both fidelity tiers use
the same transitions:

- **usage mode:** a ``health.sortie`` event per sortie carries the usage drivers (:class:`SortieUsage`);
- **telemetry mode:** health is held for the sortie; the same ``health.sortie`` event is dispatched at the end
  with the drivers computed from truth (:func:`phalanx.health.usage.usage_from_truth`); faults during the
  sortie arrive as ``health.fault`` events from M11.

**AD-26 / acceptance A3:** sensor bias (installation + drift, ``bias_*`` fields, streams ``sensor_install``
and ``sensor_drift``) and component deterioration (engine and component fields, streams ``engine_*``,
``component_build``, ``airframe_wear``) are separate latent processes with separate truth: no code path reads
one to update the other, and their random streams are disjoint (tested both ways).

**I6:** health enters the physics only through the held ports (component deltas to M07, utility states to M09,
actuator states to M05, biases to M12). A faulty run and a healthy run differ only in these state values.

Events handled (cross-module kinds per AD-44, ``configs/interfaces/w1_events.yaml``; plain top-level payload
keys, AD-48.1, :func:`phalanx.health.protocol.read_payload`):

- ``usage.sortie_summary`` (M02): advance every process by one sortie (:func:`usage_from_summary`); in usage
  mode (no ``usage`` key) also start and end the sortie in M11 and M14 (``fault_target``, ``monitor_target``)
- ``cfg.install`` / ``cfg.remove`` (M18): a unit leaves or joins a position (:data:`POSITION_STATES`); a
  removed unit's states wait on the shelf under its serial and come back with it; a new serial is built fresh
- ``mx.repaired`` (M18): the shelved unit is renewed (its next install builds a fresh unit)
- ``mx.action`` (M18): engine wash (partial recovery ρ), servicing; maintenance-induced latent defects go to
  M11 (``faults.maintenance``, :data:`LATENT_ACTIONS`)
- ``health.sortie`` (:meth:`SortieUsage.to_payload`): advance every process by one sortie (W1.5-internal)
- ``health.fault`` (``state``, ``engine``, ``delta``, ``op``): add / set / scale one hidden state (M11
  shocks, latent defects)
- ``health.maintenance`` (``action``, ``target``, ``engine``, ``serial``, ``job``): wash, overhaul, replace,
  service
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import numpy as np

from phalanx.core.events import Event
from phalanx.core.layout import VectorLayout
from phalanx.core.module import ContractError, Inputs, ModuleBase, Outputs, ParamSet, Port
from phalanx.core.rng import StreamDecl, Variate
from phalanx.core.state import Field, State, StateSchema

from . import processes as pr
from .components import AIRFRAME_PROCS, ENGINE_AUX_PROCS, Proc
from .layout import (
    ACTUATORS,
    AIRFRAME_NAMES,
    ENGINE_AUX_NAMES,
    ENGINE_DELTAS,
    N_ENGINE_AUX,
    UTILITY_SOURCES,
    BiasChannel,
    utility_entries,
)
from .protocol import LATENT_ACTIONS, POSITION_STATES, SERVICE_ACTIONS, read_payload
from .usage import SortieUsage, usage_from_summary

__all__ = [
    "ENG_F",
    "ENG_I",
    "ENG_LIFE",
    "HealthConfig",
    "HealthModule",
    "serial_value",
]

S_PER_H = 3600.0
S_PER_DAY = 86400.0

#: float state per engine
ENG_F = VectorLayout(
    (
        "foul_fan",
        "foul_hpc",
        "ero_fan",
        "ero_hpc",
        "ero_hpt",
        "ero_lpt",
        "rubin",
        "abn_hpt",
        "fod_fan_eta",
        "fod_fan_flow",
        "fod_hpc_eta",
        "fod_hpc_flow",
        *(f"init_{d}" for d in ENGINE_DELTAS),
        *(f"extra_{d}" for d in ENGINE_DELTAS),
        "coking",
        "nozzle_wear",
        "onset_energy",
        "onset_threshold",
        "onset_a",
        "onset_b",
        "spall_len",
        "spall_life",
        "debris",
        "oil_fe",
        "crack_len",
        "crack_life",
        *(f"aux_{n}" for n in ("vg_offset", "ab_spraybar", "seal_wear", "fadec_hw", "nozzle_hw")),
        "wear_debris_rate",  # W2.5 (C25): this serial's healthy-wear filter debris rate [kg/s of EOT]
        "debris_wear",  # W2.5: cumulative healthy-wear part of ``debris`` [kg]
    )
)
#: int state per engine
ENG_I = VectorLayout(("flights", "since_build", "onset", "since_onset", "spall_on", "crack_on", "build_gen"))
#: truth life consumption per engine serial (architecture §5.2 "per-serial life consumption")
ENG_LIFE = VectorLayout(
    (
        "eot_s",
        "tamp_s",
        "type1",
        "type3",
        "type4",
        "eftc",
        "src_h",
        "ps3_full",
        "ps3_partial",
        "tac",
        "ab_lights",
        "starts",
    )
)
#: airframe life counters
AIR_LIFE = VectorLayout(
    ("flight_time_s", "landings", "gear_cycles", "chute_streamings", "jfs_starts", "flights")
)
#: clock
CLOCK = VectorLayout(("n_sorties", "last_t", "n_faults", "n_maint"))

_EF = ENG_F.index
_EI = ENG_I.index
_EL = ENG_LIFE.index
_AL = AIR_LIFE.index
_CK = CLOCK.index
_AIR = {n: j for j, n in enumerate(AIRFRAME_NAMES)}
_ACT = {n: j for j, n in enumerate(ACTUATORS)}
_DELTA = {n: j for j, n in enumerate(ENGINE_DELTAS)}

# generator index per mechanism inside one (serial, sortie) unit: adding or zeroing one mechanism never shifts
# the draws of another (CRN at mechanism level)
GEN_FOUL, GEN_EROSION, GEN_COKE, GEN_NOZZLE, GEN_WEAR_DEBRIS = 0, 1, 2, 3, 4
GEN_AUX0 = 100
BUILD_INIT, BUILD_ONSET, BUILD_AB, BUILD_SPALL, BUILD_CRACK, BUILD_WEAR = 0, 1, 2, 3, 4, 5
SERIAL_DTYPE = "<U64"
#: M18 positions in state order (``pos_serial``)
POSITIONS: tuple[str, ...] = tuple(POSITION_STATES)
#: AD-44 boundary event kind -> handler
BOUNDARY_EVENTS = {
    "ops.takeoff": "_ops_takeoff",
    "usage.sortie_summary": "_summary",
    "cfg.install": "_cfg_install",
    "cfg.remove": "_cfg_remove",
    "mx.repaired": "_mx_repaired",
    "mx.action": "_mx_action",
}
#: the catalogued key that names the tail in each boundary kind (None: the kind is not tail-addressed)
TAIL_KEY: dict[str, str | None] = {
    "ops.takeoff": "tail_no",
    "usage.sortie_summary": "tail_no",
    "cfg.install": "tail",
    "cfg.remove": "tail",
    "mx.repaired": None,
    "mx.action": "tail",
}
# : airframe states whose limit (1.0) is a failure that M11 turns into a fault mode (catalogue onset
# 'triggered')
UTIL_TRIGGERS: tuple[str, ...] = (
    "hyd1_pump_wear",
    "hyd2_pump_wear",
    "hyd1_hose_fitting",
    "hyd2_hose_fitting",
    "lock_spring_l",
    "lock_spring_r",
    "lock_spring_n",
    "amagb_wear",
    "ad_heater",
)
_SERIAL_OK = str.maketrans({c: "-" for c in "_ /\\"})


def serial_value(text: str) -> str:
    """A serial string usable as an RNG key-path value (AD-37 value alphabet ``[A-Za-z0-9._:+-]``)."""
    s = text.translate(_SERIAL_OK)
    if not s or len(s) > 64:
        raise ValueError(f"bad serial {text!r}")
    return s


@dataclass(frozen=True)
class HealthConfig:
    """Instance configuration: installed engine serials and the sensor-bias channel map (from M01)."""

    engine_serials: tuple[str, ...]
    bias_channels: tuple[BiasChannel, ...]
    fault_target: str | None = None  # M11 module id: damage reaching a failure threshold emits faults.trigger
    monitor_target: str | None = None  # M14 module id: usage-mode sorties and LRU replacements are forwarded
    tail_no: str = ""  # fleet tail name of this M10 (default: the run identity's tail)

    @property
    def n_engines(self) -> int:
        return len(self.engine_serials)


def _p(params: ParamSet, name: str) -> float:
    return float(params.value(name))


class HealthModule(ModuleBase):
    """M10 (see module docstring). ``params`` is the merged ParamSet of ``configs/tejas/params/M10.yaml``."""

    version = "1.0.0"
    rate = None
    ports_in = ()
    streams = (
        StreamDecl(
            "health",
            "engine_build",
            ("scenario", "serial"),
            Variate.GENERATOR,
            owner="M10",
            description="per engine serial: build variation, onset threshold, initiation lives",
        ),
        StreamDecl(
            "health",
            "engine_wear",
            ("scenario", "serial", "sortie"),
            Variate.GENERATOR,
            owner="M10",
            description="per engine serial and sortie: deterioration increments, one generator per mechanism",
        ),
        StreamDecl(
            "health",
            "component_build",
            ("scenario", "serial"),
            Variate.GENERATOR,
            owner="M10",
            description="per component serial: incubation draws",
        ),
        StreamDecl(
            "health",
            "airframe_wear",
            ("scenario", "tail", "sortie"),
            Variate.GENERATOR,
            owner="M10",
            description="per sortie: utility/actuator wear increments (one generator per state)",
        ),
        StreamDecl(
            "health",
            "sensor_install",
            ("scenario", "serial"),
            Variate.GENERATOR,
            owner="M10",
            description="per sensor serial: installation bias (AD-07, AD-26)",
        ),
        StreamDecl(
            "health",
            "sensor_drift",
            ("scenario", "tail", "sortie"),
            Variate.NORMAL,
            block_size=256,
            owner="M10",
            description="per sortie: sensor bias drift increments indexed by bias channel (AD-26)",
        ),
    )

    def __init__(self, id: str, params: ParamSet, *, config: HealthConfig, **kw) -> None:
        self.config = config
        ne = config.n_engines
        nch = len(config.bias_channels)
        self.n_engines = ne
        self.n_bias = nch
        self.utility_names = tuple(u.name for u in utility_entries(ne))
        self.ports_out = (
            Port("engine", "1", "<f8", (ne, len(ENGINE_DELTAS))),
            Port("utility", "1", "<f8", (len(self.utility_names),)),
            Port("sensor_bias", "1", "<f8", (nch,)),
            Port("actuator", "1", "<f8", (len(ACTUATORS),)),
        )
        self.state_schema = StateSchema(
            "health.m10",
            4,  # 4: healthy-wear debris rate and cumulative wear debris per engine (W2.5, C25)
            (
                Field("eng_f", "<f8", (ne, len(ENG_F))),
                Field("eng_i", "<i8", (ne, len(ENG_I))),
                Field("eng_life", "<f8", (ne, len(ENG_LIFE))),
                Field("eng_serial", SERIAL_DTYPE, (ne,)),
                Field("air", "<f8", (len(AIRFRAME_NAMES),)),
                Field("air_aux", "<f8", (len(AIRFRAME_NAMES),)),
                Field("air_age", "<f8", (len(AIRFRAME_NAMES),)),
                Field("comp_serial", SERIAL_DTYPE, (len(AIRFRAME_NAMES) + len(ACTUATORS),)),
                Field("act", "<f8", (len(ACTUATORS),)),
                Field("bias_inst", "<f8", (nch,)),
                Field("bias_drift", "<f8", (nch,)),
                Field("sensor_serial", SERIAL_DTYPE, (nch,)),
                Field("air_life", "<f8", (len(AIR_LIFE),)),
                Field("clock", "<i8", (len(CLOCK),)),
                Field("trig", "<i8", (2 * ne + len(UTIL_TRIGGERS),)),
                Field("pos_serial", SERIAL_DTYPE, (len(POSITIONS),)),
                Field("shelf_serial", SERIAL_DTYPE, (None,)),
                Field("shelf_renew", "<i8", (None,)),
                Field("shelf_off", "<i8", (None,)),
                Field("shelf_len", "<i8", (None,)),
                Field("shelf_data", "<f8", (None,)),
                Field("sortie_open", SERIAL_DTYPE, ()),  # AD-48.2: airborne sortie ("" on the ground)
            ),
        )
        super().__init__(id, params, **kw)
        missing = [
            p.rate or p.sigma
            for p in (*AIRFRAME_PROCS, *ENGINE_AUX_PROCS)
            if (p.rate or p.sigma) and (p.rate or p.sigma) not in params
        ]
        missing += [scale for _, scale, _ in UTILITY_SOURCES.values() if scale and scale not in params]
        if missing:
            raise ContractError(f"{id}: parameters missing from the M10 set: {sorted(set(missing))}")
        self._bias_sd, self._drift_sd, self._drift_engine = self._bias_scales()

    # ------------------------------------------------------------------ configuration helpers
    def _bias_scales(self) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Per-channel installation-bias SD and drift SD (SI per sqrt second), and whether the channel drifts
        with engine operating time (engine sensors) or flight time."""
        p = self.params
        frac = _p(p, "bias_frac_span")
        speed = _p(p, "bias_speed_pct") * 100.0  # SI fraction -> percent (EU of the speed channels)
        t5 = _p(p, "bias_t5_k")
        d_t, d_o = _p(p, "drift_frac_span_temp"), _p(p, "drift_frac_span_other")
        sd, dr, eng = [], [], []
        for b in self.config.bias_channels:
            span_si = b.eu_span * b.eu_scale
            if b.quantity == "speed_percent":
                sd.append(speed * b.eu_scale)
                dr.append(0.0)  # frequency pickups: counting, no drift
            elif b.channel_id.startswith("ENG.T5.HARNESS"):
                sd.append(t5)
                dr.append(d_t * span_si)
            else:
                sd.append(frac * span_si)
                dr.append((d_t if b.quantity == "temperature" else d_o) * span_si)
            eng.append(b.channel_id.startswith("ENG."))
        return np.array(sd), np.array(dr), np.array(eng, bool)

    # ------------------------------------------------------------------ init / outputs
    def init(self, params: ParamSet, keys) -> State:
        ident = keys.identity.as_dict()
        tail = serial_value(str(ident.get("tail", "TAIL")))
        ne, nch = self.n_engines, self.n_bias
        st: dict[str, np.ndarray] = {
            "eng_f": np.zeros((ne, len(ENG_F))),
            "eng_i": np.zeros((ne, len(ENG_I)), np.int64),
            "eng_life": np.zeros((ne, len(ENG_LIFE))),
            "eng_serial": np.array([serial_value(s) for s in self.config.engine_serials], SERIAL_DTYPE),
            "air": np.zeros(len(AIRFRAME_NAMES)),
            "air_aux": np.zeros(len(AIRFRAME_NAMES)),
            "air_age": np.zeros(len(AIRFRAME_NAMES)),
            "comp_serial": np.array(
                [serial_value(f"{tail}.{n}.0") for n in (*AIRFRAME_NAMES, *ACTUATORS)], SERIAL_DTYPE
            ),
            "act": np.zeros(len(ACTUATORS)),
            "bias_inst": np.zeros(nch),
            "bias_drift": np.zeros(nch),
            "sensor_serial": np.array(
                [serial_value(f"{tail}.{b.channel_id}.0") for b in self.config.bias_channels], SERIAL_DTYPE
            ),
            "air_life": np.zeros(len(AIR_LIFE)),
            "clock": np.array([0, -1, 0, 0], np.int64),
            "trig": np.zeros(2 * ne + len(UTIL_TRIGGERS), np.int64),
            "pos_serial": np.full(len(POSITIONS), "", SERIAL_DTYPE),
            "shelf_serial": np.zeros(0, SERIAL_DTYPE),
            "shelf_renew": np.zeros(0, np.int64),
            "shelf_off": np.zeros(0, np.int64),
            "shelf_len": np.zeros(0, np.int64),
            "shelf_data": np.zeros(0),
            "sortie_open": np.array("", SERIAL_DTYPE),
        }
        for e in range(ne):
            self._build_engine(st, e)
        for j in range(len(AIRFRAME_NAMES)):
            self._build_component(st, j)
        for c in range(nch):
            st["bias_inst"][c] = self._install_bias(str(st["sensor_serial"][c]), c)
        return st

    def initial_outputs(self, state: State) -> Outputs:
        return {
            "engine": self.engine_deltas(state),
            "utility": self.utility_vector(state),
            "sensor_bias": (state["bias_inst"] + state["bias_drift"]).astype(np.float64),
            "actuator": state["act"].astype(np.float64, copy=True),
        }

    def step(self, state: State, inputs: Inputs, t: int, dt: float):  # pragma: no cover - event-only
        raise ContractError("M10 is event-only (rate=None)")

    # ------------------------------------------------------------------ derived outputs
    def engine_deltas(self, state: State) -> np.ndarray:
        """health.engine (e, 10): fractional component deltas, 0 = nominal build (W1_interfaces.md)."""
        p = self.params
        ff = _p(p, "fouling_flow_ratio")
        rf = {k: _p(p, f"erosion_flow_ratio_{k}") for k in ("fan", "hpc", "hpt", "lpt")}
        w_hpc, w_hpt = _p(p, "rubin_w_hpc"), _p(p, "rubin_w_hpt")
        out = np.zeros((self.n_engines, len(ENGINE_DELTAS)))
        sign = np.array([-1.0, -1.0, -1.0, -1.0, -1.0, 1.0, -1.0, 1.0, -1.0, 1.0])
        for e in range(self.n_engines):
            f = state["eng_f"][e]
            init = np.array([f[_EF[f"init_{d}"]] for d in ENGINE_DELTAS]) * sign
            extra = np.array([f[_EF[f"extra_{d}"]] for d in ENGINE_DELTAS])
            r = f[_EF["rubin"]]
            abn = f[_EF["abn_hpt"]]
            d = np.zeros(len(ENGINE_DELTAS))
            d[0] = -(f[_EF["foul_fan"]] + f[_EF["ero_fan"]]) + f[_EF["fod_fan_eta"]]
            d[1] = -(ff * f[_EF["foul_fan"]] + rf["fan"] * f[_EF["ero_fan"]]) + f[_EF["fod_fan_flow"]]
            d[2] = -(f[_EF["foul_hpc"]] + f[_EF["ero_hpc"]] + w_hpc * r) + f[_EF["fod_hpc_eta"]]
            d[3] = -(ff * f[_EF["foul_hpc"]] + rf["hpc"] * f[_EF["ero_hpc"]]) + f[_EF["fod_hpc_flow"]]
            d[4] = -(f[_EF["ero_hpt"]] + w_hpt * r + abn)
            d[5] = -(rf["hpt"] * (f[_EF["ero_hpt"]] + abn))
            d[6] = -f[_EF["ero_lpt"]]
            d[7] = -(rf["lpt"] * f[_EF["ero_lpt"]])
            d[8] = -f[_EF["coking"]]
            d[9] = f[_EF["nozzle_wear"]]
            out[e] = init + d + extra
        return out

    def utility_vector(self, state: State) -> np.ndarray:
        """health.utility (23,): M09's ``HEALTH_INDEX`` computed from the airframe states
        (``UTILITY_SOURCES``: an M10 wear fraction times its scale, clipped where M09 requires a fraction
        below 1)."""
        air = state["air"]
        out = np.zeros(len(self.utility_names))
        for k, name in enumerate(self.utility_names):
            src, scale, clip = UTILITY_SOURCES[name]
            v = float(air[_AIR[src]]) * (_p(self.params, scale) if scale else 1.0)
            out[k] = min(v, clip) if clip is not None else v
        return out

    def hidden_vector(self, state: State) -> np.ndarray:
        """The hidden-state inventory (``hidden_entries``): engine auxiliaries (normalised, see UtilityEntry),
        then the airframe states. Reported by the labels; not a port."""
        p = self.params
        lcf, creep = _p(p, "lcf_limit_tac"), _p(p, "creep_limit_src_h")
        out = []
        for e in range(self.n_engines):
            f = state["eng_f"][e]
            life = state["eng_life"][e]
            aux = {
                "vg_offset": f[_EF["aux_vg_offset"]],
                "ab_spraybar": f[_EF["aux_ab_spraybar"]],
                "bearing_spall": f[_EF["spall_len"]] / 0.010,
                "oil_debris": f[_EF["debris"]] / 1.0e-3,
                "seal_wear": f[_EF["aux_seal_wear"]],
                "oil_fe": f[_EF["oil_fe"]] / 1.5e-5,
                "blade_crack": f[_EF["crack_len"]] / 0.010,
                "disk_lcf": life[_EL["tac"]] / lcf,
                "blade_creep": life[_EL["src_h"]] * S_PER_H / creep,
                "tip_clearance": f[_EF["rubin"]],
                "fadec_hw": f[_EF["aux_fadec_hw"]],
                "nozzle_hw": f[_EF["aux_nozzle_hw"]],
                "fuel_nozzle": f[_EF["coking"]],
            }
            out.extend(aux[n] for n in ENGINE_AUX_NAMES)
        out.extend(state["air"].tolist())
        return np.array(out, np.float64)

    # ------------------------------------------------------------------ build draws
    def _build_engine(self, st: dict[str, np.ndarray], e: int, key: str | None = None) -> None:
        """Fresh engine build: per-serial draws from ``engine_build`` (a new serial draws its own stream; a
        renewed unit draws under ``key`` = serial + renewal number)."""
        p = self.params
        serial = key or str(st["eng_serial"][e])
        s = self.stream("engine_build", serial=serial)
        f = np.zeros(len(ENG_F))
        i = np.zeros(len(ENG_I), np.int64)
        init = s.generator(BUILD_INIT).uniform(0.0, _p(p, "init_max"), len(ENGINE_DELTAS))
        for j, d in enumerate(ENGINE_DELTAS):
            f[_EF[f"init_{d}"]] = init[j]
        g = s.generator(BUILD_ONSET)
        mu = _p(p, "onset_energy_mean")
        f[_EF["onset_threshold"]] = max(0.0, mu * (1.0 + _p(p, "onset_energy_cv") * g.standard_normal()))
        g = s.generator(BUILD_AB)
        f[_EF["onset_a"]] = g.uniform(_p(p, "onset_a_lo"), _p(p, "onset_a_hi"))
        f[_EF["onset_b"]] = g.uniform(_p(p, "onset_b_lo"), _p(p, "onset_b_hi"))
        f[_EF["spall_life"]] = pr.weibull_life(
            s.generator(BUILD_SPALL), _p(p, "bearing_weibull_shape"), _p(p, "bearing_weibull_scale")
        )
        f[_EF["crack_life"]] = pr.weibull_life(
            s.generator(BUILD_CRACK), _p(p, "crack_weibull_shape"), _p(p, "crack_weibull_scale")
        )
        # healthy-wear debris rate of this unit (W2.5, C25): fleet mean and 2 sigma of Bennett's QFDA Fe
        f[_EF["wear_debris_rate"]] = pr.gamma_rate_draw(
            s.generator(BUILD_WEAR), _p(p, "wear_debris_mean"), 0.5 * _p(p, "wear_debris_2sigma")
        )
        i[_EI["build_gen"]] = st["eng_i"][e][_EI["build_gen"]] + 1
        st["eng_f"][e] = f
        st["eng_i"][e] = i
        st["eng_life"][e] = 0.0

    def _build_component(self, st: dict[str, np.ndarray], j: int) -> None:
        name = AIRFRAME_NAMES[j]
        st["air"][j] = 0.0
        st["air_age"][j] = 0.0
        st["air_aux"][j] = 0.0
        if name.endswith("_pump_wear"):
            g = self.stream("component_build", serial=str(st["comp_serial"][j])).generator(0)
            mu = _p(self.params, "hyd_pump_onset_days")
            st["air_aux"][j] = max(
                0.0, mu * (1.0 + _p(self.params, "hyd_pump_onset_cv") * g.standard_normal())
            )

    def _install_bias(self, serial: str, c: int) -> float:
        z = self.stream("sensor_install", serial=serial).generator(0).standard_normal()
        return float(self._bias_sd[c] * z)

    # ------------------------------------------------------------------ events
    def on_event(self, state: State, event: Event, t: int):
        if event.kind == "health.sortie":
            st = self._sortie(state, SortieUsage.from_payload(event.payload), t)
            return self._triggers(st, t)
        if event.kind == "health.fault":
            return self._fault(state, event.payload), []
        if event.kind == "health.maintenance":
            return self._maintenance(state, event.payload), []
        if event.kind in BOUNDARY_EVENTS:
            d = read_payload(event.payload)
            key = TAIL_KEY[event.kind]  # the catalogued tail key of the kind (AD-48.1: read it, no fallback)
            if key is not None:
                if key not in d:
                    raise ContractError(f"{self.id}: {event.kind} payload lacks its catalogued key {key!r}")
                if str(d[key]) != self.tail_no:
                    return state, []  # a fleet-level event for another tail (one M10 per tail)
            return getattr(self, BOUNDARY_EVENTS[event.kind])(state, d, t)
        return super().on_event(state, event, t)

    # ------------------------------------------------------------------ AD-44 boundary events
    @property
    def tail_no(self) -> str:
        return self.config.tail_no or str(self.keys.identity.as_dict().get("tail", ""))

    def _ops_takeoff(self, state: State, d: Mapping, t: int):
        """``ops.takeoff`` (M02, AD-48.2): the sortie of this tail is airborne. Health is held for the
        flight (I6: only M11 perturbs it); the sortie closes with its ``usage.sortie_summary``. A take-off
        while another sortie is open, a summary of another sortie, and maintenance on the aircraft while
        airborne are protocol errors."""
        sid = serial_value(str(d["sortie_id"]))
        open_ = str(state["sortie_open"])
        if open_ and open_ != sid:
            raise ContractError(f"{self.id}: take-off of {sid!r} while sortie {open_!r} is open")
        st = self._copy(state)
        st["sortie_open"] = np.array(sid, SERIAL_DTYPE)
        return st, []

    def _airborne_guard(self, state: State, kind: str) -> None:
        if str(state["sortie_open"]):
            raise ContractError(
                f"{self.id}: {kind} on the aircraft while sortie {str(state['sortie_open'])!r} is airborne"
            )

    def _summary(self, state: State, d: Mapping, t: int):
        """``usage.sortie_summary``: one sortie of usage; usage mode also runs the sortie in M11 and M14. It
        closes the sortie opened by ``ops.takeoff`` (AD-48.2), which must be the same sortie."""
        open_ = str(state["sortie_open"])
        if open_:
            if serial_value(str(d["sortie_id"])) != open_:
                msg = f"{self.id}: summary of {d['sortie_id']!r} while sortie {open_!r} is open"
                raise ContractError(msg)
            state = {**state, "sortie_open": np.array("", SERIAL_DTYPE)}
        u = usage_from_summary(d, self.params, self.n_engines)
        st, out = self._triggers(self._sortie(state, u, t), t)
        if "usage" in d:  # telemetry mode: M11 and M14 follow the sortie through their own hooks
            return st, out
        ft = float(u.flight_time_s)
        if self.config.fault_target:
            start = {
                "sortie_id": u.sortie_id,
                "duration_s": ft,
                "window_s": 0.0,
                "ab_lights": float(sum(u.ab_lights)),
                "starts": float(sum(u.starts)),
                "landings": float(u.landings),
                "cold_jfs_starts": float(u.jfs_starts * u.cold_soak),
                "dust": float(u.dust),
                "salt": float(u.salt),
                "humidity": float(u.humidity),
                "cold_soak": float(u.cold_soak),
            }
            out.append(Event(t, "faults.sortie_start", self.config.fault_target, start, source=self.id))
            out.append(
                Event(
                    t + 1,
                    "faults.sortie_end",
                    self.config.fault_target,
                    {"flight_time_s": ft},
                    source=self.id,
                )
            )
        if self.config.monitor_target:
            pay = dict(u.to_payload())
            pay["t_start"] = max(0, t - round(ft * 1e9))
            pay["t_end"] = t
            out.append(Event(t, "monitor.usage_sortie", self.config.monitor_target, pay, source=self.id))
        return st, out

    def _items(self, pos: str) -> tuple[str, ...]:
        if pos not in POSITION_STATES:
            raise ContractError(f"{self.id}: unknown M18 position {pos!r}")
        return POSITION_STATES[pos]

    def _pack(self, st: dict[str, np.ndarray], pos: str) -> np.ndarray:
        """The hidden states of the unit at ``pos`` as one float vector (shelf layout)."""
        out: list[float] = []
        for item in self._items(pos):
            kind, _, rest = item.partition(":")
            if kind == "engine":
                e = int(rest)
                out += st["eng_f"][e].tolist() + st["eng_i"][e].astype(float).tolist()
                out += st["eng_life"][e].tolist() + st["trig"][2 * e : 2 * e + 2].astype(float).tolist()
            elif kind == "eng":
                e_s, _, name = rest.partition(":")
                out.append(float(st["eng_f"][int(e_s)][_EF[name]]))
            elif kind == "air":
                j = _AIR[rest]
                trig = (
                    st["trig"][2 * self.n_engines + UTIL_TRIGGERS.index(rest)] if rest in UTIL_TRIGGERS else 0
                )
                out += [float(st["air"][j]), float(st["air_aux"][j]), float(st["air_age"][j]), float(trig)]
        return np.asarray(out, np.float64)

    def _unpack(self, st: dict[str, np.ndarray], pos: str, v: np.ndarray) -> None:
        k = 0
        for item in self._items(pos):
            kind, _, rest = item.partition(":")
            if kind == "engine":
                e = int(rest)
                nf, ni, nl = len(ENG_F), len(ENG_I), len(ENG_LIFE)
                st["eng_f"][e] = v[k : k + nf]
                st["eng_i"][e] = np.rint(v[k + nf : k + nf + ni]).astype(np.int64)
                st["eng_life"][e] = v[k + nf + ni : k + nf + ni + nl]
                st["trig"][2 * e : 2 * e + 2] = np.rint(v[k + nf + ni + nl : k + nf + ni + nl + 2])
                k += nf + ni + nl + 2
            elif kind == "eng":
                e_s, _, name = rest.partition(":")
                st["eng_f"][int(e_s)][_EF[name]] = v[k]
                k += 1
            elif kind == "air":
                j = _AIR[rest]
                st["air"][j], st["air_aux"][j], st["air_age"][j] = v[k], v[k + 1], v[k + 2]
                if rest in UTIL_TRIGGERS:
                    st["trig"][2 * self.n_engines + UTIL_TRIGGERS.index(rest)] = round(v[k + 3])
                k += 4

    def _fresh(self, st: dict[str, np.ndarray], pos: str, serial: str, renew: int) -> None:
        """Build a new (or renewed) unit's states at ``pos``: draws keyed by serial (and renewal number)."""
        tag = f".r{renew}" if renew else ""
        for item in self._items(pos):
            kind, _, rest = item.partition(":")
            if kind == "engine":
                e = int(rest)
                st["eng_serial"][e] = serial_value(serial)
                self._build_engine(st, e, key=serial_value(serial + tag))
                st["trig"][2 * e : 2 * e + 2] = 0
            elif kind == "eng":
                e_s, _, name = rest.partition(":")
                st["eng_f"][int(e_s)][_EF[name]] = 0.0
            elif kind == "air":
                j = _AIR[rest]
                st["comp_serial"][j] = serial_value(f"{serial}.{rest}{tag}")
                self._build_component(st, j)
                if rest in UTIL_TRIGGERS:
                    st["trig"][2 * self.n_engines + UTIL_TRIGGERS.index(rest)] = 0

    @staticmethod
    def _shelf_find(st: Mapping[str, np.ndarray], serial: str) -> int:
        hit = np.flatnonzero(np.asarray(st["shelf_serial"]) == serial)
        return int(hit[0]) if hit.size else -1

    @staticmethod
    def _shelf_drop(st: dict[str, np.ndarray], r: int) -> None:
        off, n = int(st["shelf_off"][r]), int(st["shelf_len"][r])
        st["shelf_data"] = np.delete(st["shelf_data"], np.s_[off : off + n])
        st["shelf_off"] = np.where(st["shelf_off"] > off, st["shelf_off"] - n, st["shelf_off"])
        for f in ("shelf_serial", "shelf_renew", "shelf_off", "shelf_len"):
            st[f] = np.delete(st[f], r)

    def _shelf_put(self, st: dict[str, np.ndarray], serial: str, renew: int, data: np.ndarray) -> None:
        r = self._shelf_find(st, serial)
        if r >= 0:
            self._shelf_drop(st, r)
        st["shelf_serial"] = np.append(st["shelf_serial"], np.array(serial, SERIAL_DTYPE))
        st["shelf_renew"] = np.append(st["shelf_renew"], np.int64(renew))
        st["shelf_off"] = np.append(st["shelf_off"], np.int64(st["shelf_data"].size))
        st["shelf_len"] = np.append(st["shelf_len"], np.int64(data.size))
        st["shelf_data"] = np.append(st["shelf_data"], data)

    def _cfg_install(self, state: State, d: Mapping, t: int):
        self._airborne_guard(state, "cfg.install")
        st = self._copy(state)
        pos, serial = str(d["pos"]), str(d["serial"])
        items = self._items(pos)
        k = POSITIONS.index(pos)
        out: list[Event] = []
        if str(st["pos_serial"][k]) == serial:
            return st, out
        r = self._shelf_find(st, serial)
        if r >= 0 and int(st["shelf_len"][r]) > 0:  # a used unit comes back with its states
            off, n = int(st["shelf_off"][r]), int(st["shelf_len"][r])
            self._unpack(st, pos, st["shelf_data"][off : off + n].copy())
            if any(i.startswith("engine:") for i in items):
                st["eng_serial"][int(items[0].split(":")[1])] = serial_value(serial)
            self._shelf_drop(st, r)
        else:
            renew = int(st["shelf_renew"][r]) if r >= 0 else 0
            if r >= 0:
                self._shelf_drop(st, r)
            self._fresh(st, pos, serial, renew)
        st["pos_serial"][k] = serial
        if self.config.fault_target:
            out.append(
                Event(
                    t,
                    "faults.install",
                    self.config.fault_target,
                    {"pos": pos, "serial": serial},
                    source=self.id,
                )
            )
        if self.config.monitor_target:
            for item in items:
                if item.startswith("lru:"):
                    pay = {"lru": item[4:], "serial": serial}
                    out.append(
                        Event(t, "monitor.lru_replace", self.config.monitor_target, pay, source=self.id)
                    )
        return st, out

    def _cfg_remove(self, state: State, d: Mapping, t: int):
        self._airborne_guard(state, "cfg.remove")
        st = self._copy(state)
        pos, serial = str(d["pos"]), str(d["serial"])
        self._items(pos)
        k = POSITIONS.index(pos)
        r = self._shelf_find(st, serial)
        renew = int(st["shelf_renew"][r]) if r >= 0 else 0
        self._shelf_put(st, serial, renew, self._pack(st, pos))
        st["pos_serial"][k] = ""
        return st, []

    def _mx_repaired(self, state: State, d: Mapping, t: int):
        serial = str(d["serial"])
        r = self._shelf_find(state, serial)
        if r < 0:  # not a unit this tail removed (mx.repaired is fleet-level)
            return state, []
        st = self._copy(state)
        self._shelf_put(st, serial, int(st["shelf_renew"][r]) + 1, np.zeros(0))
        return st, []

    def _mx_action(self, state: State, d: Mapping, t: int):
        self._airborne_guard(state, "mx.action")
        action, pos = str(d["action"]), str(d.get("pos") or "")  # pos / job_no depend on the action
        st: dict[str, np.ndarray] = self._copy(state)
        if action in ("ENGINE_WASH", "WASH"):
            for e in range(self.n_engines):
                st = self._maintenance(st, {"action": "wash", "engine": e})
        elif action in SERVICE_ACTIONS:
            for target in SERVICE_ACTIONS[action]:
                for e in range(self.n_engines) if target == "engine_oil" else (0,):
                    st = self._maintenance(st, {"action": "service", "target": target, "engine": e})
        out: list[Event] = []
        latent = LATENT_ACTIONS.get((action, pos)) or LATENT_ACTIONS.get((action, "*"))
        if latent and self.config.fault_target:
            job = str(d.get("job_no") or f"{action}-{t}")
            pay = {"job": job, "action": latent}
            out.append(Event(t, "faults.maintenance", self.config.fault_target, pay, source=self.id))
        return st, out

    # ------------------------------------------------------------------ belief forks (phalanx.fork.belief)
    def _engine_items(self, state: State) -> list[tuple[int, str]]:
        k = POSITIONS.index("ENG")
        out = []
        for e in range(self.n_engines):
            sn = str(state["pos_serial"][k]) if e == 0 and str(state["pos_serial"][k]) else ""
            out.append((e, sn or str(state["eng_serial"][e])))
        return out

    def belief_items(self, state: State) -> list[str]:
        """BeliefTarget: the installed engine serials (their bearing-spall initiation is the Weibull item)."""
        return sorted(sn for _, sn in self._engine_items(state))

    def belief_prior(self, state: State, serial: str) -> tuple[str, Mapping[str, float]]:
        """BeliefTarget: Weibull prior of bearing-spall initiation in engine operating hours (A-W1.5-8)."""
        del state, serial
        p = self.params
        return "weibull", {
            "shape": _p(p, "bearing_weibull_shape"),
            "scale_h": _p(p, "bearing_weibull_scale") / S_PER_H,
        }

    def with_belief(self, state: State, draws: Mapping[str, Mapping[str, float]], keep_faults) -> State:
        """BeliefTarget: set each engine's operating-time clock and spall initiation life to the posterior
        draw; a spall not yet initiated under the draw is removed. Fault instances live in M11
        (``keep_faults`` is
        applied there, not here)."""
        del keep_faults
        st = self._copy(state)
        for e, sn in self._engine_items(state):
            if sn not in draws:
                continue
            u_s, th_s = float(draws[sn]["u_s"]), float(draws[sn]["th_s"])
            st["eng_life"][e][_EL["eot_s"]] = u_s
            f, i = st["eng_f"][e], st["eng_i"][e]
            f[_EF["spall_life"]] = th_s
            if th_s > u_s:
                i[_EI["spall_on"]] = 0
                f[_EF["spall_len"]] = 0.0
                f[_EF["debris"]] = f[_EF["debris_wear"]]  # the healthy-wear part stays (W2.5)
                st["trig"][2 * e + 1] = 0
        return st

    @staticmethod
    def _copy(state: State) -> dict[str, np.ndarray]:
        return {k: np.array(v, copy=True) for k, v in state.items()}

    def _sortie(self, state: State, u: SortieUsage, t: int) -> dict[str, np.ndarray]:
        if u.n_engines != self.n_engines:
            raise ContractError(
                f"{self.id}: sortie usage has {u.n_engines} engines, module has {self.n_engines}"
            )
        st = self._copy(state)
        last_t = int(st["clock"][_CK["last_t"]])
        days_s = float(t - last_t) * 1e-9 if last_t >= 0 else 0.0
        for e in range(self.n_engines):
            self._advance_engine(st, e, u)
        self._advance_airframe(st, u, days_s)
        self._advance_bias(st, u)
        al = st["air_life"]
        al[_AL["flight_time_s"]] += u.flight_time_s
        al[_AL["landings"]] += u.landings
        al[_AL["gear_cycles"]] += u.gear_cycles
        al[_AL["chute_streamings"]] += u.chute_streamings
        al[_AL["jfs_starts"]] += u.jfs_starts
        al[_AL["flights"]] += 1.0
        st["clock"][_CK["n_sorties"]] += 1
        st["clock"][_CK["last_t"]] = t
        return st

    def _advance_engine(self, st: dict[str, np.ndarray], e: int, u: SortieUsage) -> None:
        p = self.params
        f = st["eng_f"][e]
        i = st["eng_i"][e]
        life = st["eng_life"][e]
        serial = str(st["eng_serial"][e])
        s = self.stream("engine_wear", serial=serial, sortie=serial_value(u.sortie_id))
        eot, tamp = u.eot_s[e], u.tamp_s[e]
        # recoverable fouling (Wiener, drift ∝ dust index, EOT seconds)
        g = s.generator(GEN_FOUL)
        z = g.standard_normal(2)
        mu, sg = _p(p, "fouling_drift"), _p(p, "fouling_sigma")
        f[_EF["foul_fan"]] = pr.wiener_fouling(f[_EF["foul_fan"]], mu, sg, eot, u.dust, z[0])
        f[_EF["foul_hpc"]] = pr.wiener_fouling(f[_EF["foul_hpc"]], mu, sg, eot, u.dust, z[1])
        # non-recoverable erosion (gamma per engine flight x severity S x dust^k)
        g = s.generator(GEN_EROSION)
        sev = _p(p, "severity_s") * u.dust ** _p(p, "erosion_dust_exponent")
        cv, ref = _p(p, "erosion_cv"), _p(p, "erosion_ref_flights")
        flights = int(i[_EI["flights"]])
        acc = _p(p, "hpc_accel_factor") if flights >= _p(p, "hpc_accel_after") else 1.0
        for name, rate in (
            ("ero_fan", _p(p, "erosion_rate_fan")),
            ("ero_hpc", _p(p, "erosion_rate_hpc") * acc),
            ("ero_hpt", _p(p, "erosion_rate_hpt")),
            ("ero_lpt", _p(p, "erosion_rate_lpt")),
        ):
            f[_EF[name]] += pr.gamma_increment(g, rate * sev, cv, ref, 1.0)
        # rub-in after the last build
        i[_EI["since_build"]] += 1
        f[_EF["rubin"]] = pr.rub_in(
            int(i[_EI["since_build"]]), _p(p, "rubin_c0"), _p(p, "rubin_c1"), _p(p, "rubin_tau")
        )
        # abnormal onset (N-CMAPSS): usage energy vs the per-serial threshold, then exp(a (t/τ)^b) - 1
        f[_EF["onset_energy"]] += eot + _p(p, "onset_tamp_weight") * tamp
        if i[_EI["onset"]] == 0 and pr.onset_crossed(f[_EF["onset_energy"]], f[_EF["onset_threshold"]]):
            i[_EI["onset"]] = 1
            i[_EI["since_onset"]] = 0
        if i[_EI["onset"]] == 1:
            i[_EI["since_onset"]] += 1
            f[_EF["abn_hpt"]] = pr.onset_loss(
                float(i[_EI["since_onset"]]),
                f[_EF["onset_a"]],
                f[_EF["onset_b"]],
                _p(p, "onset_tau"),
                _p(p, "onset_amplitude"),
            )
        # combustor coking and nozzle area wear (gamma per EOT second)
        ccv = _p(p, "component_cv")
        rate = _p(p, "coking_rate")
        f[_EF["coking"]] += pr.gamma_increment(s.generator(GEN_COKE), rate, ccv, 1.0 / max(rate, 1e-300), eot)
        rate = _p(p, "nozzle_area_rate")
        f[_EF["nozzle_wear"]] += pr.gamma_increment(
            s.generator(GEN_NOZZLE), rate, ccv, 1.0 / max(rate, 1e-300), eot
        )
        # life consumption (truth counters per serial)
        life[_EL["eot_s"]] += eot
        life[_EL["tamp_s"]] += tamp
        for k in (
            "type1",
            "type3",
            "type4",
            "eftc",
            "src_h",
            "ps3_full",
            "ps3_partial",
            "ab_lights",
            "starts",
        ):
            life[_EL[k]] += getattr(u, k)[e]
        dtac = u.tac()[e]
        life[_EL["tac"]] += dtac
        # bearing spall: Weibull initiation in EOT, exponential growth, debris ∝ growth, oil Fe
        if i[_EI["spall_on"]] == 0 and life[_EL["eot_s"]] >= f[_EF["spall_life"]]:
            i[_EI["spall_on"]] = 1
            f[_EF["spall_len"]] = _p(p, "bearing_l0")
        dl = 0.0
        if i[_EI["spall_on"]] == 1:
            new = pr.exp_grow(f[_EF["spall_len"]], _p(p, "bearing_growth_rate"), eot)
            dl = new - f[_EF["spall_len"]]
            f[_EF["spall_len"]] = new
        ddeb = _p(p, "bearing_debris_per_length") * dl
        # healthy wear (W2.5, C25): filter debris at this unit's rate, gamma increments per EOT; it adds to
        # the filter debris only: the normal SOAP Fe slope (oil_fe_slope) already is the oil-borne part of
        # healthy wear (fine particles), so only spall debris raises oil Fe above it
        dwear = pr.gamma_increment(
            s.generator(GEN_WEAR_DEBRIS),
            float(f[_EF["wear_debris_rate"]]),
            _p(p, "wear_debris_cv"),
            _p(p, "wear_debris_ref"),
            eot,
        )
        f[_EF["debris_wear"]] += dwear
        f[_EF["debris"]] += ddeb + dwear
        f[_EF["oil_fe"]] += _p(p, "oil_fe_slope") * eot + _p(p, "oil_fe_per_debris") * ddeb
        # blade crack: Weibull initiation in TAC, Paris growth per counted N2 cycle (ΔK in MPa m^0.5)
        if i[_EI["crack_on"]] == 0 and life[_EL["tac"]] >= f[_EF["crack_life"]]:
            i[_EI["crack_on"]] = 1
            f[_EF["crack_len"]] = _p(p, "crack_a0")
        if i[_EI["crack_on"]] == 1:
            cycles = u.type1[e] + u.type3[e]
            a = pr.paris_grow(
                f[_EF["crack_len"]], cycles, _p(p, "paris_c"), _p(p, "paris_m"), _p(p, "paris_dsigma") * 1e-6
            )
            f[_EF["crack_len"]] = min(
                a, 1.0
            )  # a 1 m crack is a liberated blade; the cap only keeps it finite
        # generic engine auxiliaries
        drivers = {"eot": eot, "ab_lights": u.ab_lights[e], "flights": 1.0}
        for k, proc in enumerate(ENGINE_AUX_PROCS):
            j = _EF[f"aux_{proc.state}"]
            f[j] = self._apply(proc, f[j], s.generator(GEN_AUX0 + k), drivers[proc.driver], 1.0)
        i[_EI["flights"]] += 1

    def _apply(self, proc: Proc, x: float, g: np.random.Generator, du: float, env: float) -> float:
        p = self.params
        if proc.family == "gamma":
            rate = _p(p, proc.rate) * env
            if rate == 0.0:
                return float(x)
            return float(x + pr.gamma_increment(g, rate, _p(p, "component_cv"), 1.0 / rate, du))
        if proc.family == "wiener":
            z = float(g.standard_normal())
            return pr.wiener_fouling(x, _p(p, proc.rate), _p(p, proc.sigma), du, env, z)
        if proc.family == "wiener_signed":
            z = float(g.standard_normal())
            return float(x + _p(p, proc.sigma) * np.sqrt(du) * z)
        if proc.family == "linear":
            return float(min(1.0, x + _p(p, proc.rate) * du * env))
        if proc.family == "counter":
            return float(x + du / _p(p, proc.rate))
        if proc.family == "fault":  # no wear process: changed only by faults (health.fault) and maintenance
            return float(x)
        raise ContractError(f"unknown process family {proc.family!r}")

    def _advance_airframe(self, st: dict[str, np.ndarray], u: SortieUsage, days_s: float) -> None:
        p = self.params
        s = self.stream("airframe_wear", sortie=serial_value(u.sortie_id))
        e_ref = _p(p, "brake_energy_ref")
        air = st["air"]
        contam_f = _p(p, "contam_wear_factor")
        env = {
            "": 1.0,
            "dust": u.dust,
            "humidity": u.humidity,
            "salt_humidity": u.salt * u.humidity,
            "cold": _p(p, "jfs_cold_factor") if u.cold_soak > 0 else 1.0,
            "contam1": 1.0 + (contam_f - 1.0) * min(1.0, max(0.0, air[_AIR["hyd1_contamination"]])),
            "contam2": 1.0 + (contam_f - 1.0) * min(1.0, max(0.0, air[_AIR["hyd2_contamination"]])),
        }
        drivers = {
            "fh": u.flight_time_s,
            "eot_sum": float(sum(u.eot_s)),
            "days": days_s,
            "flights": 1.0,
            "landings": u.landings,
            "gear_cycles": u.gear_cycles,
            "jfs_starts": u.jfs_starts,
            "chute_streamings": u.chute_streamings,
            # reference stops of the sortie's (total, per wheel) brake energy (W2.1c: not x landings again)
            "brake_l": u.brake_energy_j[0] / e_ref if u.brake_energy_j[0] > 0 else u.landings,
            "brake_r": u.brake_energy_j[1] / e_ref if u.brake_energy_j[1] > 0 else u.landings,
        }
        # AD-48.6: M09 owns the in-sortie physical accrual of the main brakes and tyres; in telemetry mode
        # it replaces the per-landing surrogate (whose generator then draws nothing; others are unchanged)
        accrued = {}
        if u.brake_wear_accrued:
            accrued |= {"brake_wear_l": u.brake_wear_accrued[0], "brake_wear_r": u.brake_wear_accrued[1]}
        if u.tyre_wear_accrued:
            accrued |= {"tyre_wear_l": u.tyre_wear_accrued[0], "tyre_wear_r": u.tyre_wear_accrued[1]}
        for proc in AIRFRAME_PROCS:
            j = _AIR[proc.state]
            if proc.state in accrued:
                air[j] += accrued[proc.state]
                continue
            g = s.generator(j)
            du = drivers[proc.driver]
            if proc.family == "incubation":
                onset = st["air_aux"][j]  # per-serial incubation [s] (drawn at build)
                grow = _p(p, "hyd_pump_growth_days")  # [s] after loading
                # contamination accelerates both the remaining incubation and the growth (Pall x4)
                eff = du * env[proc.env]
                air[j] = pr.incubation_growth(air[j], st["air_age"][j], eff, onset, grow)
                st["air_age"][j] += eff
            elif proc.family == "solder":
                ratio = u.thermal_cycle_k / _p(p, "solder_dt_ref")
                air[j] += ratio ** _p(p, "solder_exponent") / _p(p, "solder_n_ref")
            elif proc.family == "nz_miner":
                air[j] += self._nz_damage(u.nz_counts)
            else:
                air[j] = self._apply(proc, air[j], g, du, env[proc.env])
        # actuators (Archard wear, TRANSFER MD-83), one generator per actuator
        rate = _p(p, "act_leak_rate")
        for k in range(len(ACTUATORS)):
            g = s.generator(1000 + k)
            st["act"][k] += pr.gamma_increment(g, rate, _p(p, "component_cv"), 1.0 / rate, u.flight_time_s)

    def _nz_damage(self, counts: Sequence[float]) -> float:
        """Miner damage of one sortie's Nz level crossings: Σ n_j / N_j, N_j = N_7g ((7 - 1) / (L_j - 1))^k
        for levels above 1 g (negative levels carry no damage in this form)."""
        p = self.params
        from .usage import NZ_LEVELS_DEFAULT

        n7, k = _p(p, "str_fatigue_n7g"), _p(p, "str_fatigue_exponent")
        dmg = 0.0
        for c, lv in zip(counts, NZ_LEVELS_DEFAULT, strict=False):
            if lv > 1.0 and c > 0:
                dmg += c / (n7 * (6.0 / (lv - 1.0)) ** k)
        return dmg

    def _advance_bias(self, st: dict[str, np.ndarray], u: SortieUsage) -> None:
        if self.n_bias == 0:
            return
        z = self.stream("sensor_drift", sortie=serial_value(u.sortie_id)).draws(0, self.n_bias)
        hours = np.where(self._drift_engine, float(sum(u.eot_s)) / max(1, self.n_engines), u.flight_time_s)
        st["bias_drift"] = st["bias_drift"] + self._drift_sd * np.sqrt(hours) * z

    def _triggers(self, st: dict[str, np.ndarray], t: int) -> tuple[dict[str, np.ndarray], list[Event]]:
        """Damage that reached its failure threshold becomes a fault (once per installed item): a
        ``faults.trigger`` event to M11 (the causal path damage -> failure; I6)."""
        out: list[Event] = []
        p = self.params
        trig = st["trig"]
        for e in range(self.n_engines):
            f = st["eng_f"][e]
            for k, (key, crit) in enumerate(
                (("eng:crack_len", "crack_critical"), ("eng:spall_len", "spall_critical"))
            ):
                j = 2 * e + k
                if trig[j] == 0 and f[_EF[key[4:]]] >= _p(p, crit):
                    trig[j] = 1
                    if self.config.fault_target:
                        out.append(
                            Event(
                                t,
                                "faults.trigger",
                                self.config.fault_target,
                                {"trigger": key, "engine": e},
                                source=self.id,
                            )
                        )
        for k, name in enumerate(UTIL_TRIGGERS):
            j = 2 * self.n_engines + k
            if trig[j] == 0 and st["air"][_AIR[name]] >= 1.0:
                trig[j] = 1
                if self.config.fault_target:
                    out.append(
                        Event(
                            t,
                            "faults.trigger",
                            self.config.fault_target,
                            {"trigger": f"util:{name}", "engine": 0},
                            source=self.id,
                        )
                    )
        return st, out

    # ------------------------------------------------------------------ faults and maintenance
    def _fault(self, state: State, payload: Mapping[str, np.ndarray]) -> dict[str, np.ndarray]:
        st = self._copy(state)
        target = str(np.asarray(payload["state"]).item())
        op = str(np.asarray(payload.get("op", np.array("add"))).item())
        delta = float(payload["delta"])
        e = int(payload.get("engine", np.array(0)))
        ref = self._resolve(st, target, e)
        arr, idx = ref
        if op == "add":
            arr[idx] = arr[idx] + delta
        elif op == "set":
            arr[idx] = delta
        elif op == "mul":
            arr[idx] = arr[idx] * delta
        else:
            raise ContractError(f"health.fault: unknown op {op!r}")
        if target == "eng:spall_len" and arr[idx] > 0:
            st["eng_i"][e][_EI["spall_on"]] = 1
        if target == "eng:crack_len" and arr[idx] > 0:
            st["eng_i"][e][_EI["crack_on"]] = 1
        st["clock"][_CK["n_faults"]] += 1
        return st

    def _resolve(self, st: dict[str, np.ndarray], target: str, e: int):
        """``eng:<field>`` (engine float state, incl. ``extra_<delta>``), ``util:<airframe state>``,
        ``act:<actuator>``."""
        kind, _, name = target.partition(":")
        if kind == "eng":
            if not 0 <= e < self.n_engines or name not in _EF:
                raise ContractError(f"health.fault: unknown engine state {target!r} (engine {e})")
            return st["eng_f"][e], _EF[name]
        if kind == "util" and name in _AIR:
            return st["air"], _AIR[name]
        if kind == "act" and name in _ACT:
            return st["act"], _ACT[name]
        raise ContractError(f"health.fault: unknown state {target!r}")

    def _maintenance(self, state: State, payload: Mapping[str, np.ndarray]) -> dict[str, np.ndarray]:
        st = self._copy(state)
        action = str(np.asarray(payload["action"]).item())
        target = str(np.asarray(payload.get("target", np.array(""))).item())
        e = int(payload.get("engine", np.array(0)))
        serial = str(np.asarray(payload.get("serial", np.array(""))).item())
        p = self.params
        if action == "wash":
            f = st["eng_f"][e]
            for k in ("foul_fan", "foul_hpc"):
                f[_EF[k]] = pr.wash(f[_EF[k]], _p(p, "wash_rho"))
        elif action == "replace_engine":
            if not serial:
                raise ContractError("replace_engine needs the new engine serial")
            st["eng_serial"][e] = serial_value(serial)
            self._build_engine(st, e)
            st["trig"][2 * e : 2 * e + 2] = 0
        elif action == "overhaul_module":
            f = st["eng_f"][e]
            if target not in ("fan", "hpc", "hpt", "lpt"):
                raise ContractError(f"overhaul_module: unknown module {target!r}")
            f[_EF[f"ero_{target}"]] *= _p(p, "overhaul_residue")
            if target in ("fan", "hpc"):
                f[_EF[f"foul_{target}"]] = 0.0
                f[_EF[f"fod_{target}_eta"]] = 0.0
                f[_EF[f"fod_{target}_flow"]] = 0.0
            if target == "hpt":
                f[_EF["abn_hpt"]] = 0.0
                f[_EF["onset_energy"]] = 0.0
                st["eng_i"][e][_EI["onset"]] = 0
                st["eng_i"][e][_EI["since_onset"]] = 0
            st["eng_i"][e][_EI["since_build"]] = 0
            f[_EF["rubin"]] = 0.0
        elif action == "replace_component":
            if target in _AIR:
                j = _AIR[target]
                st["comp_serial"][j] = serial_value(serial or f"{st['comp_serial'][j]}r")
                self._build_component(st, j)
                if target in UTIL_TRIGGERS:
                    st["trig"][2 * self.n_engines + UTIL_TRIGGERS.index(target)] = 0
            elif target in _ACT:
                k = _ACT[target]
                st["comp_serial"][len(AIRFRAME_NAMES) + k] = serial_value(serial or "act")
                st["act"][k] = 0.0
            else:
                raise ContractError(f"replace_component: unknown component {target!r}")
        elif action == "replace_sensor":
            ids = [b.channel_id for b in self.config.bias_channels]
            if target not in ids:
                raise ContractError(f"replace_sensor: unknown channel {target!r}")
            c = ids.index(target)
            st["sensor_serial"][c] = serial_value(serial or f"{st['sensor_serial'][c]}r")
            st["bias_inst"][c] = self._install_bias(str(st["sensor_serial"][c]), c)
            st["bias_drift"][c] = 0.0
        elif action == "service":
            resets = {
                "tyres": ("tyre_p_loss_l", "tyre_p_loss_r", "tyre_p_loss_n"),
                "struts": ("strut_service_l", "strut_service_r", "strut_service_n"),
                "hyd_fluid": ("hyd1_contamination", "hyd2_contamination"),
                "hyd_filters": ("hyd1_filter_loading", "hyd2_filter_loading"),
                "accumulators": ("hyd1_precharge_loss", "hyd2_precharge_loss"),
            }
            if target == "engine_oil":
                st["eng_f"][e][_EF["oil_fe"]] = 0.0
            elif target in resets:
                for n in resets[target]:
                    st["air"][_AIR[n]] = 0.0
            else:
                raise ContractError(f"service: unknown target {target!r}")
        else:
            raise ContractError(f"health.maintenance: unknown action {action!r}")
        st["clock"][_CK["n_maint"]] += 1
        return st


def merged_params(sets: Mapping[str, ParamSet], name: str = "tejas.M10") -> ParamSet:
    """Merge the M10 parameter sets into one ParamSet (names are unique across sets; checked)."""
    params = {}
    for s in sets.values():
        for k in s:
            if k in params:
                raise ContractError(f"duplicate M10 parameter {k!r}")
            params[k] = s[k]
    return ParamSet(name, params)


def load_health_params(**kw) -> ParamSet:
    from phalanx.dictionary.params import load_params

    return merged_params(load_params("M10", **kw))


#: number of engine auxiliary entries per engine in health.utility (re-exported for consumers)
ENGINE_AUX_PER_ENGINE = N_ENGINE_AUX
