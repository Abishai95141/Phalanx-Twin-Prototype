"""System builder (W2.1 deliverable 1): one aircraft's telemetry-mode truth loop, M02-M14, for one sortie.

``build_sortie_system(spec)`` builds the core ``System`` from the published ``ports.py`` bindings
(:mod:`.wiring`; never hand-wired) in the fixed Gauss-Seidel order of architecture §8:

    event-only:  scenario (M02), health (M10), faults (M11), monitor (M14), boundary holds, sortie config
    continuous:  env (M03) -> pilot (M04) -> fcs (M05) -> fadec (M08) -> eng (M07) -> af (M06) -> util (M09)
                 -> sens (M12) -> acq_fadec, acq_dfcc (M13 in-loop lanes)

Event-only modules have no inputs and only held outputs, so they go first (their edges are forward). Every
back-edge is a documented one-frame delay (``wiring.BACK_EDGES``). The continuous modules form one loop
segment (the af -> env and lane -> fcs/fadec back-edges span it); :mod:`.fused` compiles it.

**Identity and configuration hash (AD-48.8, AD-36).** The System identity is (scenario, tail, sortie = the
plan's stable RNG key). Per-tail configuration that the module ParamSets do not carry (engine and hydraulic
serials, the sortie's post-start initial conditions, the utilities' sortie configuration, the plan itself) is
the ParamSet of an event-only :class:`SortieConfig` module, so it enters ``System.config_hash`` like any
parameter.

**Telemetry window (AD-46).** Sortie telemetry starts from post-start idle: :func:`telemetry_window` cuts the
plan's PREFLIGHT and ENGINE_START segments and starts kernel time 0 at the first GROUND_IDLE instant; the
contract epoch moves with it, so UTC times are unchanged. Pre-window history enters as the initial condition:
fuel loaded (M09 configuration instead of ``util.refuel`` events), engine and pilot at post-start idle
(:mod:`.initial`). ``af.ground_elevation`` and ``fcs.pbit_start`` are still sent by M02 at the window start.

**Tracked exceptions.** A binding with no producer is an error unless it is a tracked exception of the
conformance gate (``w1_ports.yaml``); each one gets a labelled boundary source (:class:`BoundaryHold`, a PROXY
listed in ``docs/assumptions.md``). None today: ``lane.ENG.AB_LIT``, the last one, has M13's lane of the M12
UV flame detector since the W2.2 merge.
M11 effects whose target module has no handler yet are left unwired (:data:`UNHANDLED_FAULT_TARGETS`, tracked
with a stale check).
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from functools import cache
from typing import Any

import numpy as np

from phalanx.core.events import Event
from phalanx.core.module import ContractError, ModuleBase, Param, ParamSet, Port
from phalanx.core.rng import KeyPath, RngService, StreamRegistry
from phalanx.core.scheduler import Connection, System
from phalanx.core.state import StateSchema
from phalanx.core.time import ClockDomain

from .wiring import Source, TrackedException, connections, tracked_exceptions

#: architecture module number of each module id of the telemetry System (tracked exceptions name them)
M_ID: dict[str, str] = {
    "scenario": "M02",
    "env": "M03",
    "pilot": "M04",
    "fcs": "M05",
    "af": "M06",
    "eng": "M07",
    "fadec": "M08",
    "util": "M09",
    "health": "M10",
    "faults": "M11",
    "sens": "M12",
    "acq_fadec": "M13",
    "acq_dfcc": "M13",
    "monitor": "M14",
    "avio": "M12",
}
#: module id -> catalogue PREFIX of its package (ports.py)
PREFIX_OF: dict[str, str] = {
    "scenario": "scenario",
    "env": "env",
    "pilot": "pilot",
    "fcs": "fcs",
    "af": "af",
    "eng": "eng",
    "fadec": "fadec",
    "util": "util",
    "health": "health",
    "faults": "faults",
    "sens": "sens",
    "acq_fadec": "acq",
    "acq_dfcc": "acq",
    "monitor": "monitor",
    "avio": "avio",
}
EVENT_ONLY_ORDER = ("scenario", "health", "faults", "monitor")
#: Gauss-Seidel order of the continuous modules. **Proposed decision PD-W2.1a-1** (conflict reported): the
#: DFCC (M05) runs after its lanes. M05 frames at step k on the sample of [t_k, t_k+1) and reads that sample
#: from its lane input in the same step (fcs/ports.py: "a frame falls in exactly the steps where M13 delivers
#: a sample"); behind a delayed lane back-edge it reads the previous step's empty buffer (zeros: measured, see
#: tests/integration/test_integration_system.py::test_architecture_order_reads_empty_dfcc_lanes). Its plant
#: outputs reach M06, M09 and M12 through documented one-frame delays (fcs -> af/util/sens in
#: wiring.BACK_EDGES). M08 keeps its own delayed-lane contract (frames of [t_k-1, t_k) at step k).
CONTINUOUS_ORDER = ("env", "pilot", "fadec", "eng", "af", "util", "sens", "acq_fadec", "acq_dfcc", "fcs")
#: 240 Hz modules after the loop's members (M12 avionics extension, AD-51): M08 reads the ADC's P0 altitude
#: signal one frame late (W2.2 f1b3bc9: p0 <- avio.p0_from_hp, BACK_EDGES ("avio", "fadec")), so avio closes
#: the loop and is the fused group's last member (its ADC runs in the compiled loop, the rest after it)
OBSERVATION_ORDER = ("avio",)
#: M11 effect targets (FaultConfig.targets keys) -> module id
FAULT_TARGETS: dict[str, str] = {
    "health": "health",
    "sensors": "sens",
    "monitoring": "monitor",
    "fcs": "fcs",
    "utilities": "util",
    "engine": "eng",
    "fadec": "fadec",
    "airframe": "af",
    "ops": "scenario",  # ops.start_failure (AD-49): M02 ground-aborts the sortie before its take-off
}
#: M11 targets whose consumer has no handler for the catalogued kind yet (AD-48.4; owners W2.1b / W2.1c). They
# : are left unwired (M11 drops those effects, non-strict) until the handler lands; a test fails when one is
# stale.
UNHANDLED_FAULT_TARGETS: dict[str, tuple[str, str]] = {}
#: dictionary flight_phase: fine phases that are cut from the telemetry window (AD-46)
PRE_WINDOW_PHASES = ("PREFLIGHT", "ENGINE_START")


# ------------------------------------------------------------------------------------------- the plan window
def telemetry_window(plan, start_phase: str = "GROUND_IDLE") -> Any:
    """The plan from post-start idle (AD-46): segments before the first GROUND_IDLE removed, offsets and UTC
    start shifted by the cut. Raises if the plan has no GROUND_IDLE segment (a ground run, for example).

    ``start_phase`` may name a later **ground** phase (``TAXI_OUT``, ``RUNUP``) for short diagnostic windows
    that start with the engine at idle and the aircraft parked (e.g. the run-up transient of A2/A3); the cut
    segments are then ground segments at idle, so the post-start initial condition still applies."""
    from phalanx.scenario import phases as P

    allowed = {"GROUND_IDLE": (), "TAXI_OUT": ("GROUND_IDLE",), "RUNUP": ("GROUND_IDLE", "TAXI_OUT")}
    if start_phase not in allowed:
        raise ContractError(f"window start phase {start_phase!r} not in {sorted(allowed)}")
    ph = np.asarray(plan.seg_i[:, 0], dtype=np.int64)
    code = {v: k for k, v in P.FINE_NAMES.items()}[start_phase]
    idx = np.flatnonzero(ph == code)
    if idx.size == 0:
        raise ContractError(f"{plan.sortie_id}: no {start_phase} segment (no post-start idle to start from)")
    j = int(idx[0])
    cut = {P.FINE_NAMES[int(x)] for x in ph[:j]}
    if not cut <= set(PRE_WINDOW_PHASES) | set(allowed[start_phase]):
        raise ContractError(f"{plan.sortie_id}: unexpected phases before {start_phase}: {sorted(cut)}")
    t0 = int(plan.t_off_ns[j])
    return replace(
        plan,
        t_off_ns=np.asarray(plan.t_off_ns[j:], dtype=np.int64) - t0,
        seg_f=np.array(plan.seg_f[j:], dtype=np.float64),
        seg_i=np.array(plan.seg_i[j:], dtype=np.int64),
        t_end_off_ns=int(plan.t_end_off_ns) - t0,
        t_start_utc_ns=int(plan.t_start_utc_ns) + t0,
    )


# ------------------------------------------------------------------------------------------- helper modules
class SortieConfig(ModuleBase):
    """Event-only carrier of the per-tail / per-sortie configuration (AD-48.8): no ports, no state, no events.

    Its ParamSet is the run configuration the module ParamSets do not hold, so ``System.config_hash`` covers
    it.
    """

    version = "1.0.0"
    rate = None
    state_schema = StateSchema("integration.sortie_config", 1, ())

    def init(self, params, keys):
        return {}


class BoundaryHold(ModuleBase):
    """**PROXY** (A-W2.1-1): a labelled boundary source for a tracked missing producer (``w1_ports.yaml``
    exception). Event-only; its held output is a constant fixed by its ParamSet. It exists only while the
    exception is open: the conformance gate fails on the stale exception, and the builder then wires the real
    producer instead."""

    version = "1.0.0"
    rate = None
    state_schema = StateSchema("integration.boundary_hold", 1, ())

    def __init__(self, id: str, port: Port, value: float, *, signal: str, owner: str, source: str) -> None:
        self.ports_out = (port,)
        self._value = np.full(port.shape, value, dtype=np.dtype(port.dtype))
        ps = ParamSet(
            "integration.boundary_hold",
            {
                "value": Param(
                    float(value), port.unit if port.unit != "ns" else "1", "ASSUMPTION", source, True
                ),
                "signal": Param(
                    signal, "1", "ASSUMPTION", source, True, note=f"tracked exception, owner {owner}"
                ),
            },
        )
        super().__init__(id, ps)

    def init(self, params, keys):
        return {}

    def initial_outputs(self, state):
        return {self.ports_out[0].name: self._value.copy()}


# ------------------------------------------------------------------------------------------- the spec
@dataclass(frozen=True)
class SortieSpec:
    """Everything that defines one telemetry-mode sortie run (with the order log)."""

    plan: Any  # phalanx.scenario.plan.SortiePlan (the full M02 plan)
    scenario: str  # RNG scenario key
    root: int  # 128-bit root seed
    platform: str = "tejas"
    monitoring_regime: str = "immature"
    faults_stochastic: bool = True
    compiled: bool = True
    validate: bool = False  # core validation mode (read-only state, unit/shape/finiteness checks)
    purity_check: bool = False
    block_len: int = 1024
    #: build the compiled fused truth-loop group (``fused.TruthLoopGroup``); False = per-step segment path
    fused: bool = True
    hyd_units: tuple[str, str] = ("HYD1", "HYD2")
    #: first ground phase of the telemetry window (``telemetry_window``); GROUND_IDLE for a sortie
    start_phase: str = "GROUND_IDLE"
    #: diagnostic override of the continuous Gauss-Seidel order (a permutation of CONTINUOUS_ORDER; the fused
    #: group is written for CONTINUOUS_ORDER, so an override needs ``fused=False``)
    continuous_order: tuple[str, ...] | None = None
    #: record every keyed draw in a ``DrawLedger`` (I8 CRN audit across forks; tests only, it keeps all draws)
    rng_ledger: bool = False


@dataclass
class SortieSystem:
    """A built telemetry System plus what the sortie runner needs to drive and record it."""

    spec: SortieSpec
    window: Any  # SortiePlan of the telemetry window
    system: System
    modules: dict[str, Any]
    connections: list[Connection]
    exceptions_used: list[tuple[str, str, TrackedException]]
    dictionary: Any
    sensor_config: Any
    epoch_utc_ns: int
    trim: Any  # phalanx.fadec.trim.FadecTrim (post-start idle operating point)
    pla_idle: float
    initial_overrides: dict[str, Any] = field(default_factory=dict)

    @property
    def identity(self) -> KeyPath:
        return self.system.identity

    def start(self):
        """The initial world: ``System.start`` plus the post-start initial conditions M04 and the avionics ADC
        cannot take yet (the pilot's hand at the idle detent; the ADC at the field static pressure, so M08's
        P0 is right from its first frame)."""
        from .initial import adc_at_field, pilot_at_idle

        w = self.system.start()
        w.states["pilot"] = pilot_at_idle(w.states["pilot"], self.pla_idle)
        avio = self.modules.get("avio")
        if avio is not None:
            w.states["avio"] = adc_at_field(w.states["avio"], float(w.held["env.p_s"]), avio.config.adc_p)
            for name, v in avio.initial_outputs(w.states["avio"]).items():
                w.held[f"avio.{name}"] = np.asarray(v)
        return w

    def bootstrap_events(self) -> list[Event]:
        """Events the harness injects at t = 0 (core modules cannot self-start)."""
        return list(self.modules["scenario"].initial_events())


# ------------------------------------------------------------------------------------------- building
@cache
def _dictionary(platform: str):
    from phalanx.dictionary import load_dictionary

    return load_dictionary(platform=platform)


@cache
def _sensor_config(platform: str, n_engines: int):
    from phalanx.sensors.config import build_sensor_config

    return build_sensor_config(_dictionary(platform), n_engines=n_engines)


def canonical_param_set(module: str, platform: str = "tejas") -> ParamSet:
    """Every parameter set of ``module`` as one ParamSet, names ``<set>__<param>`` (F4: the canonical M12/M13
    ParamSets whose hash covers the configuration the module builds from its parameter file)."""
    from phalanx.dictionary.params import load_params

    sets = load_params(module, platform=platform)
    merged = {f"{s}__{k}": sets[s][k] for s in sorted(sets) for k in sets[s]}
    return ParamSet(f"{platform}.{module}.canonical", merged)


def _probe_initial_outputs(modules, root: int, identity: KeyPath) -> dict[str, np.ndarray]:
    """``"module.port"`` -> held output at t0 of throw-away instances bound exactly as ``System`` binds them
    (same root, identity and declared streams), so keyed initial draws equal those of the real System."""
    rng = RngService(root, StreamRegistry())
    out: dict[str, np.ndarray] = {}
    for m in modules:
        for dcl in m.streams:
            rng.registry.declare(dcl)
        m.bind(rng.scope(identity.extend(**dict(m.identity))))
        st = m.init(m.params, m.keys)
        out.update({f"{m.id}.{k}": np.asarray(v) for k, v in m.initial_outputs(st).items()})
    return out


def _ground_idle_pla(plan) -> float:
    """PLA feed-forward (rad) of the plan's first GROUND_IDLE segment: the ground-idle detent of the
    sortie."""
    from phalanx.scenario import phases as P
    from phalanx.scenario.plan import S_PLA

    j = np.flatnonzero(np.asarray(plan.seg_i[:, 0]) == P.GROUND_IDLE)
    if j.size == 0:
        raise ContractError(f"{plan.sortie_id}: no GROUND_IDLE segment")
    return float(plan.seg_f[int(j[0]), S_PLA])


def _ground_equilibrium(ic, n_eng: int, platform: str, settle_s: float = 4.0):
    """The parked aircraft's static equilibrium on its gear, from M06's own kernel: start at ``ic`` (CG at the
    uncompressed-gear guess), integrate ``settle_s`` with the reference input row, and return the IC at the
    settled height and attitude with zero velocity and rate (the struts' residual motion is < 1 mm/s; the M06
    static-equilibrium test). Avoids a free-fall artefact at t = 0 (WoW open for the first ~0.1 s)."""
    from phalanx.airframe.build import airframe_param_set, build_config
    from phalanx.airframe.ic import ic_params, initial_float_state
    from phalanx.airframe.kernel import N_I, O_ALT, O_QN0, airframe_kernel

    cfg = build_config(airframe_param_set(platform, extra=ic_params(ic)), n_eng)
    f = initial_float_state(
        ic.lat,
        ic.lon,
        ic.h,
        np.asarray(ic.vel_ned),
        np.asarray(ic.quat_nb),
        np.asarray(ic.omega_nb),
        ic.gear,
        ic.h_ground,
        cfg.dp,
    )
    n = round(settle_s * 240)
    u = np.tile(np.asarray(ic.u_ref, dtype=np.float64), (n, 1))
    _f, _i, out = airframe_kernel(
        f,
        np.zeros(N_I, dtype=np.int64),
        cfg.dp,
        cfg.ap,
        cfg.tab,
        cfg.gtab,
        cfg.ttab,
        u,
        1.0 / 240.0,
        n_eng,
        0,
    )
    q = out[-1, O_QN0 : O_QN0 + 4]
    q = q / np.sqrt(float(np.sum(q * q)))
    return replace(ic, h=float(out[-1, O_ALT]), quat_nb=tuple(float(x) for x in q))


def _isa_pressure_altitude(p: float) -> float:
    """ISA pressure altitude (m) of a static pressure (troposphere; the DFCC's initial belief on the
    ground)."""
    return 288.15 / 0.0065 * (1.0 - (p / 101325.0) ** (0.0065 * 287.05287 / 9.80665))


def _package_bindings(n_engines: int) -> dict[str, dict[str, str]]:
    """Module id -> {input port: signal} from each package's ``ports.py`` (the canonical accessor, F5).

    The submodule is imported by name: some packages re-export the ``ports`` function under the package,
    which shadows the submodule attribute (E1 F6)."""
    import importlib

    def b(pkg: str) -> dict[str, str]:
        return dict(importlib.import_module(f"phalanx.{pkg}.ports").ports(n_engines)[2])

    acq_b = b("acquisition")
    return {
        "env": b("environment"),
        "pilot": b("pilot"),
        "fcs": b("fcs"),
        "fadec": b("fadec"),
        "eng": b("engine"),
        "af": b("airframe"),
        "util": b("utilities"),
        "sens": b("sensors"),
        "acq_fadec": acq_b,
        "acq_dfcc": acq_b,
        "avio": b("sensors.avionics"),
    }


def build_sortie_system(spec: SortieSpec) -> SortieSystem:
    """Build the telemetry System of ``spec.plan`` (module docstring)."""
    from phalanx.acquisition.config import build_acquisition_config
    from phalanx.acquisition.core import STREAMS as ACQ_STREAMS
    from phalanx.acquisition.module import LaneAcquisition, lane_channels
    from phalanx.airframe.analysis import input_row
    from phalanx.airframe.geodesy import euler_to_quat
    from phalanx.airframe.ic import AirframeIC
    from phalanx.airframe.module import Airframe
    from phalanx.engine.design import build_engine_model
    from phalanx.engine.module import EngineModule
    from phalanx.environment.climatology import Ambient
    from phalanx.environment.config import load_env_config
    from phalanx.environment.module import EnvironmentModule
    from phalanx.fadec import Fadec, FadecConfig, load_fadec_params
    from phalanx.faults import FaultConfig, FaultInjector, load_catalogue, load_fault_params, load_graph
    from phalanx.fcs.module import Fcs, FcsIC
    from phalanx.health import HealthConfig, HealthModule, load_health_params, sensor_bias_channels
    from phalanx.monitoring import MonitoringConfig, MonitoringModule, load_code_table, load_monitoring_params
    from phalanx.pilot.module import PilotModule, load_pilot_config
    from phalanx.scenario.config import load_scenario_params
    from phalanx.scenario.module import ScenarioModule
    from phalanx.scenario.plan import S_HDG
    from phalanx.scenario.refuel import refuel_loads
    from phalanx.sensors.module import SensorPhysics
    from phalanx.utilities import Utilities, UtilitiesConfig, load_m09_params

    plan = spec.plan
    win = telemetry_window(plan, spec.start_phase)
    cont = tuple(spec.continuous_order) if spec.continuous_order is not None else CONTINUOUS_ORDER
    if sorted(cont) != sorted(CONTINUOUS_ORDER):
        raise ContractError(f"continuous_order must be a permutation of {CONTINUOUS_ORDER}")
    if spec.fused and cont != CONTINUOUS_ORDER:
        raise ContractError("the fused truth-loop group is written for CONTINUOUS_ORDER (use fused=False)")
    tail = plan.tail
    n_eng = len(plan.engine_serials)
    serials = tuple(plan.engine_serials)
    d = _dictionary(spec.platform)
    sens_cfg = _sensor_config(spec.platform, n_eng)
    identity = KeyPath.of(scenario=spec.scenario, tail=tail, sortie=plan.rng_key)
    epoch = int(win.t_start_utc_ns)

    # ---------------------------------------------------------------- world inputs (M02, M03, M04)
    sp = load_scenario_params(spec.platform)
    env_cfg = load_env_config(spec.platform)
    amb = Ambient.from_vector(np.asarray(win.ambient, dtype=np.float64))
    scen = ScenarioModule(
        "scenario",
        sp,
        env_cfg,
        plan=win,
        epoch_utc_ns=epoch,
        plan_targets=("env", "pilot"),
        fcs="fcs",
        airframe="af",
        utilities=None,  # fuel is loaded before the window (initial condition of M09)
        # AD-48.2 sortie lifecycle (W2.1c): ops.takeoff at the plan's take-off, ops.sortie_done at cut-off
        takeoff_targets=("health", "faults", "monitor"),
        done_targets=("faults", "monitor"),
        segment_source="pilot",  # phases and lifecycle follow the flown segments (A-W2.1-9)
        # W2.5 / W2.1a: power-up at the engine start, just before the window (PBIT of M05 and M14; M11's
        # preflight start-failure draws, whose ops.start_failure ground-aborts the sortie)
        power_up_targets=("fcs", "faults", "monitor"),
    )
    env = EnvironmentModule(
        "env",
        env_cfg,
        n_engines=n_eng,
        engine_serials=serials,
        hyd_units=spec.hyd_units,
        ambient=amb,
        compiled=spec.compiled,
    )
    pilot_cfg = load_pilot_config(spec.platform)
    # the pilot reports its (physically gated) segment changes to M02 (W2.1a take-off fix, A-W2.1-9)
    pilot = PilotModule(
        "pilot",
        pilot_cfg,
        n_engines=n_eng,
        utilities="util",
        fcs="fcs",
        segment_target="scenario",
        compiled=spec.compiled,
    )
    pla_idle = _ground_idle_pla(plan)  # the plan's ground-idle detent (S_PLA of its GROUND_IDLE segment)

    # ---------------------------------------------------------------- health (M10) and its initial outputs
    bias = sensor_bias_channels(d, sens_cfg)
    health = HealthModule(
        "health",
        load_health_params(),
        config=HealthConfig(serials, bias, fault_target="faults", monitor_target="monitor", tail_no=tail),
    )
    # the M10/M03 held outputs at t0 (same keys as in the System: identity-keyed streams, AD-37)
    held0 = _probe_initial_outputs((health, env), spec.root, identity)
    # (a module binds its keys once; rebuild the two for the real System)
    health = HealthModule(
        "health",
        load_health_params(),
        config=HealthConfig(serials, bias, fault_target="faults", monitor_target="monitor", tail_no=tail),
    )
    env = EnvironmentModule(
        "env",
        env_cfg,
        n_engines=n_eng,
        engine_serials=serials,
        hyd_units=spec.hyd_units,
        ambient=amb,
        compiled=spec.compiled,
    )

    # ---------------------------------------------------------------- utilities (M09): fuel loaded, engine
    # running
    m09_ps = load_m09_params(spec.platform)
    t_amb = float(held0["env.t_s"])
    p_amb = float(held0["env.p_s"])
    # the plan's fuel load as M02's fill-to-target refuel (AD-49) leaves it before the window: each tank up to
    # its target, stopping at the brim (M09's capacity at the fuel temperature, as its util.refuel handler)
    from phalanx.utilities.fuel import fuel_density
    from phalanx.utilities.layout import N_TANKS, P_TANK, TC_CAP
    from phalanx.utilities.params import param_vector

    p9 = param_vector(m09_ps)
    cap_m3 = np.array([p9[P_TANK + TC_CAP * N_TANKS + k] for k in range(N_TANKS)])
    brim = cap_m3 * float(fuel_density(p9, t_amb))
    fuel = np.zeros(N_TANKS)
    for k, kg in refuel_loads(win, sp):
        fuel[k] = min(float(kg), float(brim[k]))
    util_cfg = UtilitiesConfig(
        soak_temp=t_amb,
        p_amb=p_amb,
        fuel=tuple(float(x) for x in fuel),
        drop_tanks=(bool(win.drop_tanks), bool(win.drop_tanks), False),
        engine_running=True,
    )
    util = Utilities("util", m09_ps, n_engines=n_eng, config=util_cfg, compiled=spec.compiled)
    util0 = util.initial_outputs(util.init(m09_ps, None))

    # ---------------------------------------------------------------- engine + FADEC at post-start idle
    model = build_engine_model()
    fadec_ps = load_fadec_params(spec.platform)
    fadec_cfg = FadecConfig.build(fadec_ps)
    # the closed-loop operating point M08 holds at the ground-idle PLA (W2.1b trim API, AD-46): the exact
    # M07 equilibrium at the field conditions and M08's bumpless initial commands
    from phalanx.engine.steady import TrimCondition
    from phalanx.fadec.trim import initial_commands, operating_point

    cond = TrimCondition(
        t_s=t_amb,
        p_s=p_amb,
        mach=0.0,
        q_spec=float(held0["env.q_spec"]),
        w_engine=tuple(float(x) for x in np.asarray(held0["env.w_engine"], dtype=np.float64).reshape(-1)[:5]),
        bleed=float(util0["bleed_extract"][0]),
        pto=float(util0["pto_power"][0]),
        t_fuel=float(util0["fuel_inlet_t"][0]),
        health=tuple(float(x) for x in np.asarray(held0["health.engine"], dtype=np.float64)[0]),
    )
    trim = operating_point(model, fadec_cfg, math.degrees(pla_idle), cond)
    if not trim.converged:
        raise ContractError(f"{plan.sortie_id}: the post-start idle trim did not converge")
    eng = EngineModule(
        "eng",
        model,
        n_engines=n_eng,
        serials=serials,
        compiled=spec.compiled,
        init_x=trim.engine.x,
        init_u=trim.engine.u,
    )
    fadec = Fadec(
        "fadec",
        fadec_ps,
        n_engines=n_eng,
        **initial_commands(trim, n_eng),
        event_target="monitor",
        compiled=spec.compiled,
    )

    # ---------------------------------------------------------------- airframe (M06) and FCS (M05) on the
    # runway
    stn = env_cfg.climatology.station(int(win.base))
    lat, lon = math.radians(stn.lat_deg), math.radians(stn.lon_deg)
    h_g = float(win.field_elev_m)
    hdg = float(win.seg_f[0, S_HDG])
    q_nb = euler_to_quat(0.0, 0.0, hdg)
    rho0, a0, t0 = float(held0["env.rho"]), float(held0["env.a_sound"]), t_amb
    u_ref = input_row(
        n_eng,
        np.zeros(13),
        np.zeros(n_eng),
        float(util0["mass"]),
        np.asarray(util0["cg"]),
        np.asarray(util0["inertia"]),
        h_g,
        atmosphere=lambda _h: (rho0, a0, t0, p_amb),
        gear_cmd=1,
    )
    af_ic = _ground_equilibrium(
        AirframeIC(
            lat, lon, h_g + GROUND_CG_HEIGHT_M, (0.0, 0.0, 0.0), tuple(q_nb), u_ref, gear=1.0, h_ground=h_g
        ),
        n_eng,
        spec.platform,
    )
    af = Airframe.from_registry("af", af_ic, n_engines=n_eng, platform=spec.platform, compiled=spec.compiled)
    fcs = Fcs.from_registry(
        "fcs",
        FcsIC(np.zeros(13), 0.0, 0.0, _isa_pressure_altitude(p_amb), True),
        platform=spec.platform,
        compiled=spec.compiled,
    )

    # ---------------------------------------------------------------- observation layer (M12, M13 in-loop
    # lanes)
    m12_ps = canonical_param_set("M12", spec.platform)
    m13_ps = canonical_param_set("M13", spec.platform)
    sens = SensorPhysics("sens", m12_ps, sens_cfg, compiled=spec.compiled)
    lanes = {}
    for ctl in ("FADEC", "DFCC"):
        ch = lane_channels(d, sens_cfg, ctl)
        acq = build_acquisition_config(d, ch, sensor_channels=sens_cfg.channels)
        lanes[ctl] = LaneAcquisition(f"acq_{ctl.lower()}", m13_ps, sens_cfg, acq, d, compiled=spec.compiled)
    # M12 avionics extension (AD-51, W2.2): INS/GPS, AHRS, ADC computation, radar altimeter, SMS (240 Hz)
    from phalanx.sensors.avionics.config import build_avionics_config
    from phalanx.sensors.avionics.module import AvionicsSystem

    avio = AvionicsSystem("avio", build_avionics_config(platform=spec.platform), d, compiled=spec.compiled)

    # ---------------------------------------------------------------- faults (M11), monitoring (M14)
    unhandled = set(UNHANDLED_FAULT_TARGETS)
    targets = {k: v for k, v in FAULT_TARGETS.items() if k not in unhandled}
    faults = FaultInjector(
        "faults",
        load_fault_params(),
        config=FaultConfig(
            load_catalogue(),
            load_graph(),
            targets,
            serials,
            bias,
            realise_physics_edges=False,
            stochastic=spec.faults_stochastic,
            tail_no=tail,
        ),
    )
    mon_ps = load_monitoring_params()
    codes = load_code_table(d, mon_ps)
    mon_cfg = MonitoringConfig.from_dictionary(
        d, codes, serials, regime=spec.monitoring_regime, tail_no=tail, epoch_utc_ns=epoch
    )
    monitor = MonitoringModule("monitor", mon_ps, config=mon_cfg)

    # ---------------------------------------------------------------- sortie configuration record (config
    # hash)
    cfg_params = {
        "tail_no": Param(tail, "1", "ASSUMPTION", RUN_SOURCE),
        "engine_serials": Param(np.array(serials), "1", "ASSUMPTION", RUN_SOURCE),
        "hyd_units": Param(np.array(spec.hyd_units), "1", "ASSUMPTION", RUN_SOURCE),
        "sortie_id": Param(plan.sortie_id, "1", "ASSUMPTION", RUN_SOURCE),
        "plan_t_off_ns": Param(np.asarray(win.t_off_ns, dtype=np.int64), "ns", "ASSUMPTION", RUN_SOURCE),
        "plan_seg_f": Param(np.asarray(win.seg_f, dtype=np.float64), "1", "ASSUMPTION", RUN_SOURCE),
        "plan_seg_i": Param(np.asarray(win.seg_i, dtype=np.int64), "1", "ASSUMPTION", RUN_SOURCE),
        "plan_t_end_off_ns": Param(int(win.t_end_off_ns), "ns", "ASSUMPTION", RUN_SOURCE),
        "epoch_utc_ns": Param(epoch, "ns", "ASSUMPTION", RUN_SOURCE),
        "ambient": Param(np.asarray(win.ambient, dtype=np.float64), "1", "ASSUMPTION", RUN_SOURCE),
        "pilot_traits": Param(np.asarray(win.pilot_traits, dtype=np.float64), "1", "ASSUMPTION", RUN_SOURCE),
        "util_fuel_kg": Param(fuel, "kg", "ASSUMPTION", RUN_SOURCE),
        "util_soak_temp": Param(t_amb, "K", "ASSUMPTION", RUN_SOURCE),
        "util_p_amb": Param(p_amb, "Pa", "ASSUMPTION", RUN_SOURCE),
        "util_drop_tanks": Param(int(win.drop_tanks), "1", "ASSUMPTION", RUN_SOURCE),
        "engine_trim": Param(
            np.concatenate([trim.engine.x, trim.engine.u, [trim.pla_deg, float(trim.regime)]]),
            "1",
            "ASSUMPTION",
            INITIAL_SOURCE,
            False,
        ),
        "pilot_pla_idle": Param(pla_idle, "rad", "ASSUMPTION", INITIAL_SOURCE, True),
        "monitoring_regime": Param(spec.monitoring_regime, "1", "ASSUMPTION", RUN_SOURCE),
        "faults_stochastic": Param(bool(spec.faults_stochastic), "1", "ASSUMPTION", RUN_SOURCE),
        "platform": Param(spec.platform, "1", "ASSUMPTION", RUN_SOURCE),
        "unwired_fault_targets": Param(np.array(sorted(unhandled)), "1", "ASSUMPTION", RUN_SOURCE),
    }
    cfgmod = SortieConfig("sortie_config", ParamSet("integration.sortie_config", cfg_params))

    # ---------------------------------------------------------------- order, wiring, System
    mods = {
        "scenario": scen,
        "health": health,
        "faults": faults,
        "monitor": monitor,
        "env": env,
        "pilot": pilot,
        "fcs": fcs,
        "fadec": fadec,
        "eng": eng,
        "af": af,
        "util": util,
        "sens": sens,
        "acq_fadec": lanes["FADEC"],
        "acq_dfcc": lanes["DFCC"],
        "avio": avio,
    }
    bindings = _package_bindings(n_eng)
    bindings = {mid: {p.name: b[p.name] for p in mods[mid].ports_in} for mid, b in bindings.items()}
    # tracked exceptions (none since the W2.2 ENG.AB_LIT producer): a labelled PROXY boundary source each,
    # shaped like the first consumer port bound to the signal (A-W2.1-1)
    exc = tracked_exceptions("e1" if n_eng == 1 else ("e2" if n_eng == 2 else "e4"))
    holds: list[BoundaryHold] = []
    boundary: dict[str, Source] = {}
    for e in exc:
        port = next(p for mid, b in bindings.items() for p in mods[mid].ports_in if b[p.name] == e.signal)
        hid, pname = "hold_" + e.signal.split(".")[-1].lower(), e.signal.replace(".", "_").lower()
        holds.append(
            BoundaryHold(
                hid,
                Port(pname, port.unit, port.dtype, port.shape, port.rate),
                0.0,
                signal=e.signal,
                owner=e.owner,
                source=f"PROXY A-W2.1-1: tracked missing producer ({e.source})",
            )
        )
        boundary[e.signal] = Source(hid, pname)
    order = [mods[m] for m in EVENT_ONLY_ORDER] + [*holds, cfgmod] + [mods[m] for m in cont]
    order += [mods[m] for m in OBSERVATION_ORDER]
    lane_ports = {lanes[c].id: lanes[c].lane_bindings() for c in lanes}
    conns, used = connections(
        order,
        bindings,
        PREFIX_OF,
        lane_ports,
        m_id=M_ID,
        exceptions=exc,
        boundary=boundary,
    )
    registry = StreamRegistry(list(ACQ_STREAMS))  # the recorder shares the lane streams (M13 README)
    if spec.rng_ledger:
        from phalanx.core.rng import DrawLedger

        rng = RngService(spec.root, registry, ledger=DrawLedger())
    else:
        rng = RngService(spec.root, registry)
    fused = ()
    if spec.fused:
        from .fused import TruthLoopGroup

        fused = (TruthLoopGroup(mods, (*CONTINUOUS_ORDER, *OBSERVATION_ORDER), conns),)
    system = System(
        order,
        conns,
        rng=rng,
        identity=identity,
        fused=fused,
        dict_hash=d.dict_hash,
        validate=spec.validate,
        purity_check=spec.purity_check,
        block_len=spec.block_len,
    )
    mods.update({h.id: h for h in holds})
    mods["sortie_config"] = cfgmod
    return SortieSystem(
        spec=spec,
        window=win,
        system=system,
        modules=mods,
        connections=conns,
        exceptions_used=used,
        dictionary=d,
        sensor_config=sens_cfg,
        epoch_utc_ns=epoch,
        trim=trim,
        pla_idle=pla_idle,
    )


#: CG height above the runway at rest on the gear [ASSUMPTION: the M06 static-equilibrium test settles
#: below the uncompressed 1.85 m from 1.75 m (tests/integration/test_airframe_ground.py); the struts settle in
#: < 1 s]
GROUND_CG_HEIGHT_M = 1.75
RUN_SOURCE = "run configuration of the telemetry sortie (W2.1a system builder; AD-48.8 config hash)"
INITIAL_SOURCE = (
    "post-start initial condition: M07+M08 from the W2.1b trim API (fadec.trim.operating_point); M04 at the "
    "ground-idle detent (phalanx.integration.initial.pilot_at_idle; M04 initial-condition API requested) "
    "[A-W2.1-3]"
)

__all__ = [
    "CONTINUOUS_ORDER",
    "EVENT_ONLY_ORDER",
    "FAULT_TARGETS",
    "M_ID",
    "OBSERVATION_ORDER",
    "PREFIX_OF",
    "UNHANDLED_FAULT_TARGETS",
    "BoundaryHold",
    "SortieConfig",
    "SortieSpec",
    "SortieSystem",
    "build_sortie_system",
    "canonical_param_set",
    "telemetry_window",
]

_ = (Mapping, Sequence, ClockDomain)
