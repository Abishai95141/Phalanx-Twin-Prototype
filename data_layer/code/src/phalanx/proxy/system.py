"""The proxy-mode ``System`` (W2.4a): DASHlink replay drivers + M08 <-> M07 -> M12 -> M13 lanes, wired from
the published bindings only (U4: no hand-wiring).

Gauss-Seidel order: scenario -> env -> pilot -> af -> boundary -> noab -> fadec -> eng -> sens -> acq. Every
input port of every module is connected from its ``bindings`` signal ``<prefix>.<name>`` to the producer of
that prefix (``replay.PRODUCER_IDS``) and port ``<name>``; the FADEC lanes ``lane.<channel_id>`` connect to
the M13 lane module through the documented one-frame-delayed back-edge (``fadec.coupling.LANE_EDGE_NOTE``).
:func:`wiring_problems` checks that every input is served by a producer port of identical shape, dtype and
unit: the proxy conformance gate (tested with no exception).

The engine starts trimmed at the record's first flight condition (:func:`trim_engine`; AD-46: telemetry starts
from post-start running conditions); M08 starts from the trim commands (bumpless bootstrap at its first
frame).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace

import numpy as np

from phalanx.acquisition.module import LaneAcquisition
from phalanx.core.module import ParamSet
from phalanx.core.rng import KeyPath, RngService, StreamRegistry
from phalanx.core.scheduler import Connection, System
from phalanx.core.units import units_compatible
from phalanx.engine.layout import U_A8, U_NAMES, U_VG1, U_VG2, U_WF, X_N2
from phalanx.engine.module import EngineModule
from phalanx.engine.steady import design_inputs, steady_state
from phalanx.environment.atmosphere import geopotential_altitude, profile_tp, ussa76_profile
from phalanx.environment.module import EnvironmentReplay
from phalanx.fadec.coupling import LANE_EDGE_NOTE
from phalanx.fadec.module import Fadec
from phalanx.pilot.module import PilotReplay
from phalanx.scenario.replay import ReplayInputs, ScenarioReplay
from phalanx.sensors.module import SensorPhysics, input_bindings

from .config import ProxyConfig
from .replay import PRODUCER_IDS, AirframeReplay, NoAfterburnerLane, ProxyBoundary, static_temperature

ORDER = ("scenario", "env", "pilot", "af", "boundary", "noab", "fadec", "eng", "sens", "acq")


@dataclass(frozen=True)
class Trim:
    """Engine trim at a flight condition: state, inputs, and the condition itself."""

    x: np.ndarray
    u: np.ndarray
    t_s: float
    p_s: float
    mach: float
    n2c25: float


def ambient(cfg: ProxyConfig, pressure_alt_m: float, mach: float, tat_k: float) -> tuple[float, float]:
    """(T_s, p_s) of the replay convention (``EnvironmentReplay``): ISA pressure at the pressure altitude,
    static temperature from TAT with unit recovery."""
    c = cfg.env.constants
    prof, n = ussa76_profile(cfg.env.layers, c)
    _t, p = profile_tp(prof, n, geopotential_altitude(float(pressure_alt_m), c.r0), c.vector())
    return float(static_temperature(np.array(tat_k), np.array(mach))), float(p)


def trim_engine(
    cfg: ProxyConfig, rec: ReplayInputs, j: int = 0, *, bleed_kgs: float = 0.0, pto_w: float = 0.0
) -> Trim:
    """Steady proxy engine at sample ``j`` of the record, at M08's demand for the highest recorded PLA of the
    engines, by continuation from the SLS design point (corrected speed first, then the ambient, with the
    customer bleed and power off-take of that sample moved in with the ambient). All engines start from this
    state (M07 takes one initial state), so the others decelerate to their own levers: a deceleration moves
    the fan away from its stall line, an acceleration from a lower lever's trim would move it towards it
    (W2.4a-2: ground idle sits on the scaled map's stall line, A-W2.4a-9/-21)."""
    m = cfg.engine
    t_s, p_s = ambient(cfg, rec.pressure_alt_m[j], rec.mach[j], rec.tat_k[j])
    mach = float(rec.mach[j])
    tb = cfg.fadec.tables
    # the demand table breakpoints are in rad (parameters are SI): M08's demand at the recorded engine-1 lever
    n2c25 = float(np.interp(float(np.max(rec.pla_rad[:, j])), tb.n2c_pla_x, tb.n2c_pla_y))
    n2_100 = float(m.params.value("n2_100pct"))
    u = design_inputs(m)
    s = steady_state(m, u)
    d = m.design.derived
    f = 1.0
    target_frac = n2c25 * n2_100 * np.sqrt(s.aux_dict()["t25"] / 288.15) / d["n2_des"]
    while f > target_frac + 1e-9:  # SLS: walk down in corrected speed
        f = max(target_frac, f - 0.01)
        s = steady_state(m, u, x0=s.x, target=("n2", f * d["n2_des"]))
    for a in np.linspace(0.0, 1.0, 11)[1:]:  # walk the ambient from SLS to the condition
        ua = design_inputs(m)
        ua[U_NAMES.index("t_s")] = 288.15 + a * (t_s - 288.15)
        ua[U_NAMES.index("p_s")] = 101325.0 + a * (p_s - 101325.0)
        ua[U_NAMES.index("mach")] = a * mach
        ua[U_NAMES.index("t_fuel")] = ua[U_NAMES.index("t_s")] + 15.0
        ua[U_NAMES.index("bleed_extract")] = a * bleed_kgs
        ua[U_NAMES.index("pto_power")] = a * pto_w
        for _ in range(3):  # physical target from the corrected demand at the current T25
            n2 = n2c25 * n2_100 * np.sqrt(s.aux_dict()["t25"] / 288.15)
            s = steady_state(m, ua, x0=s.x, target=("n2", n2))
        if not s.converged:
            raise RuntimeError(f"trim did not converge at ambient fraction {a}")
    return Trim(
        s.x.copy(),
        s.u.copy(),
        t_s,
        p_s,
        mach,
        float(s.x[X_N2] / np.sqrt(s.aux_dict()["t25"] / 288.15) / n2_100),
    )


@dataclass
class ProxySystem:
    """A wired proxy System and its parts."""

    system: System
    modules: dict
    connections: list[Connection]
    rec: ReplayInputs
    trim: Trim


def _connections(mods: Mapping[str, object]) -> list[Connection]:
    conns: list[Connection] = []
    acq: LaneAcquisition = mods["acq"]
    lane_ports = {sig: f"acq.{port}" for sig, port in acq.lane_bindings().items()}
    noab = mods["noab"]
    lane_ports["lane.ENG.AB_LIT"] = f"{noab.id}.{noab.port}"
    for mid in ORDER:
        m = mods[mid]
        if mid == "sens":
            b = input_bindings(m.config)
        elif mid == "acq":
            b = acq.bindings()
        else:
            b = dict(getattr(m, "bindings", {}) or {})
        for port, sig in b.items():
            if sig.startswith("lane."):
                if sig not in lane_ports:
                    raise KeyError(f"{mid}.{port}: no M13 lane producer for {sig}")
                conns.append(Connection(lane_ports[sig], f"{mid}.{port}", True, LANE_EDGE_NOTE))
                continue
            prefix, name = sig.split(".", 1)
            src = PRODUCER_IDS[prefix]
            conns.append(Connection(f"{src}.{name}", f"{mid}.{port}"))
    return conns


def wiring_problems(mods: Mapping[str, object], conns: list[Connection]) -> list[str]:
    """Every input port of every module is fed by exactly one connection from an existing producer port with
    the same shape and dtype and a compatible unit (the proxy conformance gate)."""
    probs: list[str] = []
    outs = {f"{mid}.{p.name}": p for mid, m in mods.items() for p in m.ports_out}
    fed: dict[str, int] = {}
    for c in conns:
        fed[c.dst] = fed.get(c.dst, 0) + 1
        src = outs.get(c.src)
        dmod, dport = c.dst.split(".", 1)
        dst = {p.name: p for p in mods[dmod].ports_in}.get(dport)
        if src is None:
            probs.append(f"{c.dst}: producer port {c.src} does not exist")
            continue
        if dst is None:
            probs.append(f"{c.dst}: not an input port")
            continue
        if tuple(src.shape) != tuple(dst.shape):
            probs.append(f"{c.dst}: shape {tuple(dst.shape)} != producer {c.src} {tuple(src.shape)}")
        if np.dtype(src.dtype) != np.dtype(dst.dtype):
            probs.append(f"{c.dst}: dtype {dst.dtype} != producer {src.dtype}")
        if not units_compatible(src.unit, dst.unit):
            probs.append(f"{c.dst}: unit {dst.unit} incompatible with producer {src.unit}")
    for mid, m in mods.items():
        for p in m.ports_in:
            k = f"{mid}.{p.name}"
            if fed.get(k, 0) != 1:
                probs.append(f"{k}: fed by {fed.get(k, 0)} connections")
    return probs


def effective_lever(cfg: ProxyConfig, rec: ReplayInputs, *, at_floor: bool = True) -> ReplayInputs:
    """The replay record with the levers M08 is fed: the recorded PLA (or, with the A/T floor option and
    ``at_floor``, the idle stop while the A/T is engaged) through the configuration's demand pre-map
    (``proxy.demand``; the MEASURED flight-condition terms of the fuel-control law). Only the pilot replay
    reads ``pla_rad``; the record is returned unchanged without a pre-map."""
    if cfg.premap is None:
        return rec
    fed = cfg.premap.lever_fed(rec.pla_rad, rec.at_engage) if at_floor else rec.pla_rad
    pla = cfg.premap.effective_pla(fed, rec.pressure_alt_m / 0.3048, rec.mach, rec.tat_k - 273.15)
    return replace(rec, pla_rad=pla)


def build_proxy_system(
    cfg: ProxyConfig,
    rec: ReplayInputs,
    *,
    identity: KeyPath,
    root: int,
    fadec_params: ParamSet | None = None,
    trim: Trim | None = None,
    validate: bool = False,
    block_len: int = 240,
    fused: bool = False,
    bleed_kgs: np.ndarray | None = None,
    pto_w: float = 0.0,
) -> ProxySystem:
    """The proxy System for one replay record (see the module docstring). ``fused=True`` runs the closed loop
    through the compiled ``loop.ProxyLoopGroup`` (bitwise equal to the modules; tested). ``bleed_kgs``
    (n_engines, n) and ``pto_w`` feed ``util.bleed_extract`` / ``util.pto_power`` (``proxy.bleed``)."""
    if rec.n_engines != cfg.n_engines:
        raise ValueError(f"record has {rec.n_engines} engines, configuration {cfg.n_engines}")
    b0 = 0.0 if bleed_kgs is None else float(np.asarray(bleed_kgs)[0, 0])
    # the trim takes the demand of the recorded lever (pre-mapped); M08 is then fed the idle stop while the
    # A/T is engaged (A/T floor option), so an A/T-engaged start begins at the recorded operating point
    rec_trim = effective_lever(cfg, rec, at_floor=False)
    tr = trim if trim is not None else trim_engine(cfg, rec_trim, bleed_kgs=b0, pto_w=pto_w)
    rec = effective_lever(cfg, rec)
    e = cfg.n_engines
    fad = Fadec(
        "fadec",
        fadec_params if fadec_params is not None else cfg.fadec_params,
        n_engines=e,
        clock=cfg.clock,
        autothrottle=True,
        initial_wf=[tr.u[U_WF]] * e,
        initial_a8=[tr.u[U_A8]] * e,
        initial_vg=[[tr.u[U_VG1], tr.u[U_VG2]]] * e,
    )
    if cfg.premap is not None and cfg.premap.at_floor:
        # M08 option (W2.4a-2): the A/T demand floored at the fed lever's demand, the pre-mapped idle stop
        fad.config = fad.config.with_cfg(at_floor_lever=1)
    mods = {
        "scenario": ScenarioReplay("scenario", rec),
        "env": EnvironmentReplay(
            "env",
            cfg.env,
            pressure_alt_m=rec.pressure_alt_m,
            mach=rec.mach,
            tat_k=rec.tat_k,
            rate_hz=rec.rate_hz,
            t0_ns=rec.t0_ns,
            n_engines=e,
            engine_serials=cfg.serials,
        ),
        "pilot": PilotReplay("pilot", rec),
        "af": AirframeReplay("af", rec),
        "boundary": ProxyBoundary("boundary", rec, cfg.sensors.n_ch, bleed_kgs=bleed_kgs, pto_w=pto_w),
        "noab": NoAfterburnerLane("noab", e, cfg.clock),
        "fadec": fad,
        "eng": EngineModule("eng", cfg.engine, n_engines=e, serials=cfg.serials, init_x=tr.x, init_u=tr.u),
        "sens": SensorPhysics("sens", cfg.m12_params, cfg.sensors),
        "acq": LaneAcquisition("acq", cfg.m13_params, cfg.sensors, cfg.lanes, cfg.dictionary),
    }
    conns = _connections(mods)
    probs = wiring_problems(mods, conns)
    if probs:
        raise ValueError("proxy wiring problems:\n" + "\n".join(probs))
    rng = RngService(int(root), StreamRegistry())
    groups = ()
    if fused:
        from .loop import ProxyLoopGroup

        groups = (ProxyLoopGroup(mods),)
    syst = System(
        [mods[k] for k in ORDER],
        conns,
        rng=rng,
        identity=identity,
        fused=groups,
        validate=validate,
        purity_check=validate,
        block_len=block_len,
    )
    return ProxySystem(syst, mods, conns, rec, tr)


__all__ = [
    "ORDER", "ProxySystem", "Trim", "ambient", "build_proxy_system", "effective_lever", "trim_engine",
    "wiring_problems",
]  # fmt: skip
