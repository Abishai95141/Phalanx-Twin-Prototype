"""Tejas ground-run bench (W2.5): the real engine/FADEC/utilities/health/fault/sensor/acquisition modules of one
tail, running on the ground, wired from their published bindings, with the faults entering only through the
physics (I6).

Why a ground run: the full aircraft (W2.1a) does not take off yet, and the released fault-signature evidence
this work package compares against is a ground (test-cell) evidence set: the CF-18 Muir matrix and the C26
magnitudes are test-cell cross-plots, corrected to inlet conditions (Muir et al., AGARD-CP-448 paper 7). An
engine run with the aircraft chocked is also an IAF practice (M02 mission GROUND_RUN, phase code 14).

Modules (all real, unmodified): M10 ``HealthModule`` (health.*), M11 ``FaultInjector`` (scripted faults only,
telemetry mode), M14 ``MonitoringModule`` (BIT, FADEC codes), M08 ``Fadec``, M07 ``EngineModule``, M09
``Utilities``, M12 ``SensorPhysics`` (the full Tejas sensor configuration), M13 ``LaneAcquisition`` (FADEC
lanes) and, after the run, the M13 recording entry point ``AcquisitionRecorder`` (every M12 channel and the
FADEC-computed channels M08 supplies, AD-42) giving the recorded values a ground station would decode.

Boundary producers (BENCH BOUNDARY, labelled; not models of coupled dynamics):
- ``scenario`` / ``env`` / ``pilot``: the published replay producers (``ScenarioReplay``, ``EnvironmentReplay``
  with its keyed process disturbances AD-32, ``PilotReplay``) driven by a ground-run schedule: phase
  GROUND_RUN, field at ISA sea level, a PLA programme;
- ``af``: a chocked, stationary aircraft: all angles and rates 0, specific force (0, 0, -g), weight on all
  wheels, wheels stopped, no brake energy. This is the exact kinematic state of a parked aircraft, not an
  approximation of airframe dynamics;
- ``fcs``: control surfaces at neutral with no hydraulic flow demand (a static FCS on the ground);
- ``noab``: the FADEC AB flame-detector lane reads 0, used only when M13 does not publish ``lane.ENG.AB_LIT``.
  The W2.5 results were generated before W2.2's producer (M12 UV flame detector -> M13 FADEC lane) was merged,
  with this zero lane; the bench never selects AB (PLA stays below the AB minimum), so 0 was the truth. Since
  the merge the bench uses the real lane.

The engine starts trimmed at the first PLA (``phalanx.fadec.trim.operating_point``, AD-46: telemetry starts
from post-start running conditions) and M08 bootstraps from the trim commands. The power-up of the sortie is
``ops.power_up`` at t = 0 to M11 and M14 (the catalogued event M02 will emit, W2.1a).

Identity: ``KeyPath(scenario, tail, sortie)``; a healthy and a faulty run of the same identity share every
exogenous draw (CRN), so they differ only through the fault's physics.
"""

from __future__ import annotations

import hashlib
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import numpy as np

SRC = Path(__file__).resolve().parents[3] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from phalanx.acquisition.config import build_acquisition_config  # noqa: E402
from phalanx.acquisition.core import STREAMS as ACQ_STREAMS  # noqa: E402
from phalanx.acquisition.module import LaneAcquisition, lane_channels  # noqa: E402
from phalanx.acquisition.record import AcquisitionRecorder, frames_from_trace  # noqa: E402
from phalanx.core.events import Event  # noqa: E402
from phalanx.core.module import ModuleBase, ParamSet, Port  # noqa: E402
from phalanx.core.rng import KeyPath, RngService, StreamRegistry  # noqa: E402
from phalanx.core.scheduler import Connection, System  # noqa: E402
from phalanx.core.state import StateSchema  # noqa: E402
from phalanx.core.time import RG_240  # noqa: E402
from phalanx.dictionary import load_dictionary  # noqa: E402
from phalanx.dictionary.params import load_param_set  # noqa: E402
from phalanx.engine.design import build_engine_model  # noqa: E402
from phalanx.engine.module import EngineModule  # noqa: E402
from phalanx.engine.steady import TrimCondition  # noqa: E402
from phalanx.environment.config import load_env_config  # noqa: E402
from phalanx.environment.module import EnvironmentReplay  # noqa: E402
from phalanx.fadec import load_fadec_params  # noqa: E402
from phalanx.fadec.coupling import LANE_EDGE_NOTE  # noqa: E402
from phalanx.fadec.module import Fadec  # noqa: E402
from phalanx.fadec.ports import P0_ENV  # noqa: E402
from phalanx.fadec.ports import RECORDED as FADEC_RECORDED  # noqa: E402
from phalanx.fadec.trim import initial_commands, operating_point  # noqa: E402
from phalanx.faults import FaultConfig, FaultInjector, load_catalogue, load_fault_params, load_graph  # noqa: E402
from phalanx.health import HealthConfig, HealthModule, load_health_params, sensor_bias_channels  # noqa: E402
from phalanx.health.protocol import plain_payload  # noqa: E402
from phalanx.monitoring import (  # noqa: E402
    MonitoringConfig,
    MonitoringModule,
    load_code_table,
    load_monitoring_params,
)
from phalanx.pilot.module import PilotReplay  # noqa: E402
from phalanx.proxy.replay import NoAfterburnerLane  # noqa: E402
from phalanx.scenario.replay import ReplayInputs, ScenarioReplay  # noqa: E402
from phalanx.sensors.config import build_sensor_config  # noqa: E402
from phalanx.sensors.module import SensorPhysics, input_bindings  # noqa: E402
from phalanx.utilities.module import Utilities, UtilitiesConfig  # noqa: E402
from phalanx.utilities.params import load_m09_params  # noqa: E402

__all__ = [
    "BENCH_CHANNELS",
    "ORDER",
    "BenchRun",
    "GroundRun",
    "bench_identity",
    "run_bench",
]

NS = 10**9
G0 = 9.80665
PHASE_GROUND_RUN = 14  # dictionary flight_phase code table (synthetic fighter phases 8-15, AD-49)
REPLAY_HZ = 4.0
ORDER = (
    "scenario",
    "env",
    "pilot",
    "af",
    "fcs",
    "health",
    "faults",
    "m14",
    "noab",
    "fadec",
    "eng",
    "util",
    "sens",
    "acq",
)
#: catalogue prefix -> producer module id (bindings are published as "<prefix>.<port>")
PRODUCERS = {
    "scenario": "scenario",
    "env": "env",
    "pilot": "pilot",
    "af": "af",
    "fcs": "fcs",
    "health": "health",
    "fadec": "fadec",
    "eng": "eng",
    "util": "util",
}
#: back-edges (consumer runs before the producer): one-frame delays, documented (architecture §8)
BACK_EDGE = {
    ("eng", "util"): "M09 utility loads (bleed, PTO, fuel inlet) seen by M07 one truth frame late: M09 is driven "
    "by M07's N2 in the same frame (N2 is the master variable, report §3), so this edge closes the loop",
}


@dataclass(frozen=True)
class GroundRun:
    """A ground-run programme: PLA breakpoints ``(t_s, pla_deg)`` held piecewise constant, the duration and the
    field condition (ISA sea level by default)."""

    duration_s: float
    pla: tuple[tuple[float, float], ...] = ((0.0, 18.0),)
    t_amb_k: float = 288.15
    regime: str = "immature"

    def pla_at(self, t_s: np.ndarray) -> np.ndarray:
        ts = np.array([p[0] for p in self.pla])
        vs = np.array([p[1] for p in self.pla])
        idx = np.searchsorted(ts, np.asarray(t_s), side="right") - 1
        return vs[np.clip(idx, 0, len(vs) - 1)]


def bench_identity(scenario: str, tail: str, sortie: str) -> KeyPath:
    return KeyPath.of(scenario=scenario, tail=tail, sortie=sortie)


# ------------------------------------------------------------------------------------------ boundaries
class GroundAirframe(ModuleBase):
    """BENCH BOUNDARY: the airframe signals of a chocked, stationary aircraft (exact for a parked aircraft)."""

    version = "1.0.0"
    rate = RG_240
    state_schema = StateSchema("bench.ground_af", 1, ())

    def __init__(self, id: str, field_elev_m: float = 0.0) -> None:
        import importlib

        ap = importlib.import_module("phalanx.airframe.ports")
        self.ports_in = ()
        self.ports_out = tuple(ap.ports(1)[1])
        self.field_elev_m = float(field_elev_m)
        super().__init__(id, ParamSet("bench.ground_af", {}))

    def init(self, params, keys):
        return {}

    def _values(self) -> dict[str, np.ndarray]:
        out: dict[str, np.ndarray] = {}
        for p in self.ports_out:
            out[p.name] = np.zeros(p.shape, dtype=np.dtype(p.dtype))
        out["quat"] = np.array([1.0, 0.0, 0.0, 0.0])
        out["f_spec_body"] = np.array([0.0, 0.0, -G0])
        out["nz"] = np.array(1.0)
        out["wow"] = np.ones(3, dtype=np.int64)
        out["alt"] = np.array(self.field_elev_m)
        out["pos_geo"] = np.array([0.0, 0.0, self.field_elev_m])
        return out

    def initial_outputs(self, state):
        return self._values()

    def step(self, state, inputs, t, dt):
        return {}, self._values()


class StaticFcs(ModuleBase):
    """BENCH BOUNDARY: FCS surfaces at neutral and no hydraulic flow demand (static FCS on the ground)."""

    version = "1.0.0"
    rate = RG_240
    state_schema = StateSchema("bench.static_fcs", 1, ())

    def __init__(self, id: str) -> None:
        import importlib

        fp = importlib.import_module("phalanx.fcs.ports")
        outs = {p.name: p for p in fp.ports(1)[1]}
        self.ports_in = ()
        self.ports_out = (outs["surf_pos"], outs["hyd_flow_demand"])
        super().__init__(id, ParamSet("bench.static_fcs", {}))

    def init(self, params, keys):
        return {}

    def initial_outputs(self, state):
        return {"surf_pos": np.zeros(13), "hyd_flow_demand": np.zeros(2)}

    def step(self, state, inputs, t, dt):
        return {}, self.initial_outputs(state)


# ------------------------------------------------------------------------------------------ static parts
@lru_cache(maxsize=1)
def _static():
    d = load_dictionary()
    sens_cfg = build_sensor_config(d)
    model = build_engine_model()
    fparams = load_fadec_params()
    from phalanx.fadec import FadecConfig

    fcfg = FadecConfig.build(fparams)
    codes = load_code_table(d, load_monitoring_params())
    lanes = lane_channels(d, sens_cfg, "FADEC")
    acq_lanes = build_acquisition_config(d, lanes, sensor_channels=sens_cfg.channels)
    rec_ids = tuple(sens_cfg.channels) + tuple(FADEC_VALUE_CHANNELS.values())
    acq_rec = build_acquisition_config(d, rec_ids, sensor_channels=sens_cfg.channels)
    return d, sens_cfg, model, fparams, fcfg, codes, acq_lanes, acq_rec


#: M08's recorded value channels (AD-42 RECORDED; the discrete words are not part of the bench recording)
FADEC_VALUE_CHANNELS = {p: c for p, c in FADEC_RECORDED.items() if p in ("n1_v", "n2_v", "t1_v", "ps3_v", "t5_avg")}


@lru_cache(maxsize=64)
def _trim(pla_deg: float, t_amb_k: float, condition: TrimCondition | None = None):
    """M08's operating point at the first PLA: at ``condition`` when given (DEVIATIONS D3: the run's own
    initial engine inputs), else the pre-registered healthy no-load condition at the field temperature."""
    _, _, model, _, fcfg, *_ = _static()
    cond = TrimCondition(t_s=t_amb_k) if condition is None else condition
    tr = operating_point(model, fcfg, pla_deg, cond)
    if not tr.converged:
        raise RuntimeError(f"bench trim did not converge at PLA {pla_deg}")
    return tr


#: the M07 input ports whose producers are not M08 (the engine's exogenous inputs at a trim)
_TRIM_INPUTS = (
    "env.t_s",
    "env.p_s",
    "env.q_spec",
    "env.w_engine",
    "util.bleed_extract",
    "util.pto_power",
    "util.fuel_inlet_t",
    "health.engine",
)


def initial_condition(
    gr: GroundRun,
    identity: KeyPath,
    events: Sequence[Event] = (),
    *,
    root: int = 0x5EED_25,
    health_params: ParamSet | None = None,
    fault_params: ParamSet | None = None,
    window_s: float = 0.5,
) -> TrimCondition:
    """DEVIATIONS D3: the engine's own exogenous inputs at the start of this run (``TrimCondition``).

    A first pass of the same bench (pre-registered trim, power-up and ``events``) runs ``window_s``; the
    condition is the window mean of the field and process inputs (M03), M09's bleed, PTO and fuel-inlet
    temperature, and the last frame of M10's ``health.engine`` (build deltas plus any fault set at t = 0). The
    run then starts trimmed there, i.e. an engine that was running at this health and these loads before the
    recording starts (AD-46), instead of a healthy no-load trim stepped into its loads and faults at t = 0."""
    system, _mods, _rng = build_bench(gr, identity, root=root, health_params=health_params, fault_params=fault_params)
    w = system.inject(system.start(), [*power_up_event(identity), *events])
    _w, tr = system.run(w, max(1, int(round(window_s * 240))), mode="block", record=list(_TRIM_INPUTS))

    def col(name: str) -> np.ndarray:
        a = np.asarray(tr.ports[name], np.float64)
        return a.reshape(a.shape[0], -1)

    return TrimCondition(
        t_s=float(col("env.t_s")[:, 0].mean()),
        p_s=float(col("env.p_s")[:, 0].mean()),
        q_spec=float(col("env.q_spec")[:, 0].mean()),
        w_engine=tuple(float(x) for x in col("env.w_engine").mean(axis=0)[:5]),
        bleed=float(col("util.bleed_extract")[:, 0].mean()),
        pto=float(col("util.pto_power")[:, 0].mean()),
        t_fuel=float(col("util.fuel_inlet_t")[:, 0].mean()),
        health=tuple(float(x) for x in col("health.engine")[-1, :10]),
    )


def bench_channels() -> tuple[str, ...]:
    """Every recorded channel of the bench (M12 channels, then the M08 computed value channels)."""
    return _static()[7].channels


BENCH_CHANNELS = None  # resolved lazily by bench_channels() (dictionary load)


# ------------------------------------------------------------------------------------------ the run
@dataclass
class BenchRun:
    """Outputs of one bench run.

    ``value`` / ``truth`` / ``validity`` / ``t_sample`` / ``flags``: per recorded channel (EU, the restricted
    truth companion, the validity code, the kernel acquisition instant, acquisition flags); ``rate_hz``: the
    channel's nominal acquisition rate; ``ports``: the recorded truth ports (SI, per truth step);
    ``m14``: M14's final state (outbox); ``faults``: M11's final state; ``n_steps``; ``input_digest``: per
    recorded channel, a blake2b digest of its acquisition input (the M12 output frames s and x, or the M08
    computed value), for the paired pipeline-invariance check."""

    identity: KeyPath
    value: dict[str, np.ndarray]
    truth: dict[str, np.ndarray]
    validity: dict[str, np.ndarray]
    t_sample: dict[str, np.ndarray]
    flags: dict[str, np.ndarray]
    rate_hz: dict[str, float]
    ports: dict[str, np.ndarray]
    m14: dict[str, np.ndarray]
    faults: dict[str, np.ndarray]
    n_steps: int
    phase: np.ndarray = field(repr=False, default_factory=lambda: np.zeros(0, np.int64))
    input_digest: dict[str, str] = field(default_factory=dict)


TRUTH_PORTS = (
    "eng.n1",
    "eng.n2",
    "eng.t2",
    "eng.t5",
    "eng.ps3",
    "eng.p5",
    "eng.wf",
    "eng.w2",
    "eng.thrust",
    "eng.a8",
    "eng.oil_t",
    "util.hyd_p",
    "util.hyd_t",
    "util.bus_v",
    "util.gen_online",
    "fadec.active_limiter",
)


def _connections(mods: Mapping[str, ModuleBase], sens_cfg) -> list[Connection]:
    conns: list[Connection] = []
    acq: LaneAcquisition = mods["acq"]
    lane_src = {sig: f"acq.{port}" for sig, port in acq.lane_bindings().items()}
    noab = mods["noab"]
    lane_src.setdefault("lane.ENG.AB_LIT", f"noab.{noab.port}")  # the real M13 lane when it exists (W2.2)
    pos = {m: k for k, m in enumerate(ORDER)}
    for mid in ORDER:
        m = mods[mid]
        if mid == "sens":
            b = input_bindings(sens_cfg)
        elif mid == "acq":
            b = acq.bindings()
        else:
            b = dict(getattr(m, "bindings", {}) or {})
        for port, sig in b.items():
            if sig.startswith("lane."):
                conns.append(Connection(lane_src[sig], f"{mid}.{port}", True, LANE_EDGE_NOTE))
                continue
            prefix, name = sig.split(".", 1)
            src_id = "sens" if prefix == "sens" else PRODUCERS[prefix]
            src = f"{src_id}.{name}"
            if pos[src_id] > pos[mid]:
                conns.append(Connection(src, f"{mid}.{port}", True, BACK_EDGE[(mid, src_id)]))
            else:
                conns.append(Connection(src, f"{mid}.{port}"))
    return conns


def _replay(gr: GroundRun, epoch_utc_ns: int) -> ReplayInputs:
    n = int(np.ceil(gr.duration_s * REPLAY_HZ)) + 2
    t = np.arange(n) / REPLAY_HZ
    pla = np.deg2rad(gr.pla_at(t))[None, :]
    return ReplayInputs(
        t0_ns=0,
        rate_hz=REPLAY_HZ,
        epoch_utc_ns=epoch_utc_ns,
        pla_rad=pla,
        phase=np.full(n, PHASE_GROUND_RUN, np.int64),
        pressure_alt_m=np.zeros(n),
        mach=np.zeros(n),
        tat_k=np.full(n, gr.t_amb_k),
        at_engage=np.zeros(n, np.int64),
        at_n1_cmd=np.zeros((1, n)),
    )


def build_bench(
    gr: GroundRun,
    identity: KeyPath,
    *,
    root: int = 0x5EED_25,
    health_params: ParamSet | None = None,
    fault_params: ParamSet | None = None,
    epoch_utc_ns: int = 1_790_035_200 * NS,
    trim_condition: TrimCondition | None = None,
):
    """(System, modules, RngService) of one bench run (see the module docstring). ``trim_condition``: the
    engine's initial trim condition (DEVIATIONS D3, ``initial_condition``); None = pre-registered trim."""
    d, sens_cfg, model, fparams, _fcfg, codes, acq_lanes, _ = _static()
    ident = identity.as_dict()
    tail = str(ident["tail"])
    serial = f"IN20-{tail}"
    tr = _trim(float(gr.pla[0][1]), float(gr.t_amb_k), trim_condition)
    rec = _replay(gr, epoch_utc_ns)
    bias = sensor_bias_channels(d)
    mods: dict[str, ModuleBase] = {
        "scenario": ScenarioReplay("scenario", rec),
        "env": EnvironmentReplay(
            "env",
            load_env_config(),
            pressure_alt_m=rec.pressure_alt_m,
            mach=rec.mach,
            tat_k=rec.tat_k,
            rate_hz=rec.rate_hz,
            n_engines=1,
            engine_serials=(serial,),
        ),
        "pilot": PilotReplay("pilot", rec, gear_down_phases=(PHASE_GROUND_RUN,)),
        "af": GroundAirframe("af"),
        "fcs": StaticFcs("fcs"),
        "health": HealthModule(
            "health",
            health_params or load_health_params(),
            config=HealthConfig((serial,), bias, fault_target="faults", tail_no=tail),
        ),
        "faults": FaultInjector(
            "faults",
            fault_params or load_fault_params(),
            config=FaultConfig(
                load_catalogue(),
                load_graph(),
                {
                    "health": "health",
                    "sensors": "sens",
                    "monitoring": "m14",
                    "utilities": "util",
                    "engine": "eng",
                    "fadec": "fadec",
                },
                (serial,),
                bias,
                realise_physics_edges=False,  # telemetry mode (PD-W1.5-1)
                stochastic=False,  # scripted faults only: the bench injects what it tests
                tail_no=tail,
            ),
        ),
        "m14": MonitoringModule(
            "m14",
            load_monitoring_params(),
            config=MonitoringConfig.from_dictionary(d, codes, (serial,), regime=gr.regime, tail_no=tail),
        ),
        "noab": None,  # set below (needs the FADEC clock)
        # P0 from the field static pressure (the bench has no avionics module; on the ground the ADC reads it
        # within its position error). W2.2 bound the Tejas default to avio.p0_from_hp, which the bench lacks
        # (W2.3a fix: the bench raised KeyError "avio" after the W2.2/W2.5 merges)
        "fadec": Fadec(
            "fadec", fparams, event_target="m14", p0_source=P0_ENV, **initial_commands(tr.engine)
        ),
        "eng": EngineModule(
            "eng", model, n_engines=1, serials=(serial,), init_x=tr.engine.x, init_u=tr.engine.u
        ),
        "util": Utilities(
            "util",
            load_m09_params(),
            n_engines=1,
            config=UtilitiesConfig(soak_temp=gr.t_amb_k, engine_running=True),
        ),
        "sens": SensorPhysics("sens", load_param_set("M12", "constants"), sens_cfg),
        "acq": LaneAcquisition("acq", load_param_set("M13", "noise_n2"), sens_cfg, acq_lanes, d),
    }
    mods["noab"] = NoAfterburnerLane("noab", 1, mods["fadec"].clock)
    conns = _connections(mods, sens_cfg)
    rng = RngService(int(root), StreamRegistry(list(ACQ_STREAMS)))
    system = System([mods[k] for k in ORDER], conns, rng=rng, identity=identity)
    return system, mods, rng


def power_up_event(identity: KeyPath, t_ns: int = 0) -> list[Event]:
    ident = identity.as_dict()
    doc = {"tail_no": str(ident["tail"]), "sortie_id": str(ident["sortie"]), "engine_starts": 1, "cold_soak": 0}
    return [Event(t_ns, "ops.power_up", tgt, plain_payload(doc), source="bench") for tgt in ("faults", "m14")]


def shutdown_event(identity: KeyPath, t_ns: int) -> list[Event]:
    """DEVIATIONS D4: the ground run's shut-down, ``ops.sortie_done`` (AD-48.2) to M14 at ``t_ns``. M14 is
    event-driven: its CBIT tests are evaluated on their grid up to the next event it receives (in the aircraft,
    the ``monitor.observe`` CIR chunks and the sortie end), so a bench run that never closes the sortie leaves
    the tests after the last event unevaluated. A ground run has no take-off: flight hours, landings and
    cycles 0, one engine start. M11 is not a consumer here (it never opened a sortie: no ``ops.takeoff``)."""
    ident = identity.as_dict()
    doc = {
        "sortie_id": str(ident["sortie"]),
        "tail_no": str(ident["tail"]),
        "t_takeoff": 0,
        "t_landing": 0,
        "flight_hours": 0.0,
        "landings": 0,
        "engine_cycles": 0,
        "engine_starts": 1,
        "chute_streamed": 0,
        "mission_type": "GROUND_RUN",
        "crew_id": "bench",
        "aborted": False,
    }
    return [Event(int(t_ns), "ops.sortie_done", "m14", plain_payload(doc), source="bench")]


def run_bench(
    gr: GroundRun,
    identity: KeyPath,
    events: Sequence[Event] = (),
    *,
    root: int = 0x5EED_25,
    health_params: ParamSet | None = None,
    fault_params: ParamSet | None = None,
    chunk_s: float = 20.0,
    record_channels: bool = True,
    trim_at_start: bool = False,
) -> BenchRun:
    """Run one ground run (power-up at t = 0, then ``events``) and record every channel (M13 recording).
    ``trim_at_start``: start trimmed at the run's own initial engine inputs (DEVIATIONS D3); the same rule for
    the healthy and the faulty run of a pair (one generation path)."""
    d, sens_cfg, *_rest = _static()
    acq_rec = _rest[-1]
    cond = None
    if trim_at_start:
        cond = initial_condition(
            gr, identity, events, root=root, health_params=health_params, fault_params=fault_params
        )
    system, mods, rng = build_bench(
        gr, identity, root=root, health_params=health_params, fault_params=fault_params, trim_condition=cond
    )
    w = system.inject(system.start(), [*power_up_event(identity), *events])
    n_total = int(round(gr.duration_s * 240))
    sens_ports = [f"sens.{p.name}" for p in mods["sens"].ports_out]
    fadec_ports = [f"fadec.{p}" for p in FADEC_VALUE_CHANNELS]
    record = [*sens_ports, "scenario.phase", *fadec_ports, *TRUTH_PORTS]
    recorder = AcquisitionRecorder(acq_rec, rng.scope(identity))
    rstate = recorder.init_state()
    records = None
    ports: dict[str, list[np.ndarray]] = {p: [] for p in TRUTH_PORTS}
    phases: list[np.ndarray] = []
    chunk = int(round(chunk_s * 240))
    m12_index = {cid: int(i) for cid, i in zip(acq_rec.channels, acq_rec.sensor_index, strict=True)}
    hashes = {cid: hashlib.blake2b(digest_size=16) for cid in acq_rec.channels}
    k0 = 0
    while k0 < n_total:
        n = min(chunk, n_total - k0)
        w, tr = system.run(w, n, mode="block", record=record)
        for p in TRUTH_PORTS:
            ports[p].append(tr.ports[p])
        phases.append(tr.ports["scenario.phase"])
        if record_channels:
            S, X = frames_from_trace(sens_cfg, tr.ports, "sens")
            ext = {}
            for port, cid in FADEC_VALUE_CHANNELS.items():
                v = np.asarray(tr.ports[f"fadec.{port}"], np.float64).reshape(n, -1)[:, 0]
                ext[cid] = (v, v)
            rstate, records = recorder.process(
                rstate, k0, S, X, tr.ports["scenario.phase"], external=ext, records=records
            )
            for cid, h in hashes.items():
                i = m12_index[cid]
                if i >= 0:
                    h.update(np.ascontiguousarray(S[:, i]).tobytes())
                    h.update(np.ascontiguousarray(X[:, i]).tobytes())
                else:
                    h.update(np.ascontiguousarray(ext[cid][0]).tobytes())
        k0 += n
    out = {k: np.concatenate(v) for k, v in ports.items()}
    value, truth, validity, t_sample, flags, rate = {}, {}, {}, {}, {}, {}
    if record_channels and records is not None:
        for c, cid in enumerate(acq_rec.channels):
            r = records[cid]
            value[cid] = r.cat("value", np.float64)
            truth[cid] = r.cat("truth", np.float64)
            validity[cid] = r.cat("validity", np.int64)
            t_sample[cid] = r.cat("t_sample", np.int64)
            flags[cid] = r.cat("flags", np.int64)
            rate[cid] = float(acq_rec.domains[int(acq_rec.domain_of[c])].clock.f_nom_hz)
    return BenchRun(
        identity=identity,
        value=value,
        truth=truth,
        validity=validity,
        t_sample=t_sample,
        flags=flags,
        rate_hz=rate,
        ports=out,
        m14={k: np.array(v, copy=True) for k, v in w.states["m14"].items()},
        faults={k: np.array(v, copy=True) for k, v in w.states["faults"].items()},
        n_steps=n_total,
        phase=np.concatenate(phases),
        input_digest={cid: h.hexdigest() for cid, h in hashes.items()} if record_channels else {},
    )
