"""TEST FIXTURES for the M09 tests (never imported by src/): ISA conditions, input builders, a scripted
input-source module, and an engine-start spool. Other test tiers import this file by path.

Everything here is a labelled TEST FIXTURE standing in for neighbouring modules at the M09 boundary
(_w1_common.md §2 "Neighbours"): the real M03/M05/M06/M07 coupling is W2.1's job.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pytest

from phalanx.core.events import Event
from phalanx.core.module import ModuleBase, ParamSet, Port
from phalanx.core.rng import KeyPath, RngService, StreamRegistry
from phalanx.core.scheduler import Connection, System
from phalanx.core.state import StateSchema
from phalanx.core.time import RG_240, TRUTH_DT_S
from phalanx.utilities import Utilities, UtilitiesConfig, load_m09_params, ports
from phalanx.utilities import layout as L

G0 = 9.80665
N2_100 = 16810.0 * 2.0 * np.pi / 60.0  # rad/s at 100 % N2 (dictionary channel_reference)
DT = TRUTH_DT_S


def isa(alt_m: float, dt_isa: float = 0.0) -> tuple[float, float, float]:
    """ISA (troposphere) static temperature K, pressure Pa, density kg/m3 at geopotential altitude
    (fixture)."""
    t_std = 288.15 - 0.0065 * alt_m
    p = 101325.0 * (t_std / 288.15) ** 5.25588
    t = t_std + dt_isa
    return t, p, p / (287.05287 * t)


def bind(
    m: Utilities, *, root: int = 0x5EED, scenario: str = "w14", tail: str = "T1", sortie: int = 1
) -> Utilities:
    """Bind identity-keyed RNG streams to a standalone module (System does this in integration)."""
    m.bind(
        RngService(root, StreamRegistry(m.streams)).scope(
            KeyPath.of(scenario=scenario, tail=tail, sortie=sortie)
        )
    )
    return m


def module(
    config: UtilitiesConfig | None = None, params: ParamSet | None = None, *, n_engines: int = 1, **kw
):
    ps = params if params is not None else load_m09_params()
    m = bind(Utilities("util", ps, n_engines=n_engines, config=config, **kw))
    return m, m.init(ps, None)


def inputs(
    n: int = 1,
    *,
    ne: int = 1,
    n2f: float | np.ndarray = 0.95,
    p3: float | np.ndarray = 6.0e5,
    t3: float | np.ndarray = 700.0,
    wf: float | np.ndarray = 0.6,
    wf_ab: float | np.ndarray = 0.0,
    demand: float | np.ndarray = 0.0,
    fspec: tuple[float, float, float] | np.ndarray = (0.0, 0.0, -G0),
    tas: float | np.ndarray = 200.0,
    mach: float | np.ndarray = 0.6,
    wow: tuple[int, int, int] | np.ndarray = (0, 0, 0),
    wheel: tuple[float, float] | np.ndarray = (0.0, 0.0),
    pbrk: tuple[float, float] | np.ndarray = (0.0, 0.0),
    alt: float = 3000.0,
    t_s: float | None = None,
    w_hyd: float = 0.0,
    w_bp: float = 0.0,
    health: np.ndarray | None = None,
) -> dict[str, np.ndarray]:
    """TEST FIXTURE input block (leading tick axis n). Scalars broadcast; arrays of length n are per tick."""
    ts, ps, rho = isa(alt)
    if t_s is not None:
        rho = ps / (287.05287 * t_s)
        ts = t_s

    def per_tick(v, width=None):
        a = np.asarray(v, dtype=np.float64)
        if width is None:
            return np.broadcast_to(a, (n,)).copy() if a.ndim <= 1 and a.size in (1, n) else a
        if a.ndim == 1 and a.size == width:
            return np.tile(a, (n, 1))
        if a.ndim == 1 and a.size == n:
            return np.repeat(a[:, None], width, axis=1)
        return np.broadcast_to(a, (n, width)).copy()

    hv = np.zeros(L.N_HEALTH) if health is None else np.asarray(health, dtype=np.float64)
    return {
        "n2": per_tick(np.asarray(n2f) * N2_100, ne),
        "bleed_p3": per_tick(p3, ne),
        "bleed_t3": per_tick(t3, ne),
        "wf": per_tick(np.asarray(wf) / ne, ne),
        "wf_ab": per_tick(np.asarray(wf_ab) / ne, ne),
        "hyd_flow_demand": per_tick(demand, 2),
        "f_spec_body": per_tick(np.asarray(fspec, dtype=np.float64), 3),
        "tas": per_tick(tas),
        "mach": per_tick(mach),
        "wow": per_tick(np.asarray(wow, dtype=np.float64), 3).astype(np.int64),
        "wheel_speed": per_tick(np.asarray(wheel, dtype=np.float64), 2),
        "brake_energy_rate": per_tick(np.asarray(pbrk, dtype=np.float64), 2),
        "t_s": np.full(n, ts),
        "p_s": np.full(n, ps),
        "rho": np.full(n, rho),
        "w_hyd": np.full((n, 2), w_hyd),
        "w_bleed_pto": np.full((n, ne), w_bp),
        "health_utility": np.tile(hv, (n, 1)),
    }


def run(m: Utilities, st, inp: dict, k0: int = 0):
    """Run a block of len(inp['tas']) ticks; returns (state, outputs)."""
    n = inp["tas"].shape[0]
    return m.step_block(st, inp, np.arange(k0, k0 + n, dtype=np.int64), DT)


def event(kind: str, **payload) -> Event:
    return Event(0, kind, "util", payload)


# ------------------------------------------------------------------------------------------------ manoeuvres
S_REF = 38.4  # m^2 Tejas wing area [DIRECT, R §1]
T_MAX_AB = 84.0e3  # N F404-IN20 max AB thrust [DIRECT]
T_MIL = 54.0e3  # N dry thrust (aggregator + closure, R §1)
WF_MAX_AB = 4.3  # kg/s (AB SFC ~1.8 lb/lbf/h on the -400 base x 84 kN; engine note, order of magnitude)
WF_MIL = 1.0  # kg/s (F404-400 MIL ~7,739-8,270 lb/h, R §4)


def climb_profile(
    theta_deg: float,
    thrust: float,
    *,
    mass: float = 8300.0,
    v0: float = 230.0,
    alt: float = 3000.0,
    seconds: float = 45.0,
    cd0: float = 0.022,
    k_ind: float = 0.12,
) -> tuple[np.ndarray, np.ndarray]:
    """TEST FIXTURE point-mass longitudinal manoeuvre at constant pitch (flight-path angle = pitch).

    Speed evolves with dV/dt = (T - D)/m - g sin(theta), drag D = q S (cd0 + k CL^2) with CL from
    n = cos(theta); the body specific force is f_x = (T - D)/m, f_z = -g cos(theta). A zoom bleeds speed and
    keeps f_x high, a level max-AB run gains speed and drag so f_x decays. Returns (fspec[n, 3], tas[n]) at
    240 Hz.
    """
    th = np.radians(theta_deg)
    _, _, rho = isa(alt)
    n = round(seconds * 240)
    fs = np.zeros((n, 3))
    tas = np.zeros(n)
    v = v0
    for j in range(n):
        q = 0.5 * rho * v * v
        cl = mass * G0 * np.cos(th) / max(q * S_REF, 1.0)
        drag = q * S_REF * (cd0 + k_ind * cl * cl)
        fx = (thrust - drag) / mass
        fs[j] = (fx, 0.0, -G0 * np.cos(th))
        tas[j] = v
        v = max(v + DT * (fx - G0 * np.sin(th)), 60.0)
    return fs, tas


# ------------------------------------------------------------------------------------------------ engine
# start
@dataclass
class EngineStartFixture:
    """TEST FIXTURE engine HP spool for JFS start tests (stands in for M07/M08 start behaviour).

    I_HP = 3 kg m^2 (W1.3a brief); PTO power converts to torque with the M09 speed floor
    (``P = T (w + w_floor)``); windage drag ``drag_cut * (w / w_cut)^2``; light-off at 20 % N2 (T-50 timeline,
    R §4) with combustion torque ramping to ``t_comb`` by 65 % N2; held at idle (65 % N2) once reached.
    ``lit=False`` is a dry rollover (motoring only).
    """

    lit: bool = True
    i_hp: float = 3.0
    drag_cut: float = 40.0
    t_comb: float = 120.0
    idle: float = 0.65
    w: float = 0.0
    fuel_on: bool = False

    def advance(self, pto_power: float, w_floor: float = 1.0) -> float:
        w_cut = 0.55 * N2_100
        torque = -pto_power / (self.w + w_floor) - self.drag_cut * (self.w / w_cut) ** 2
        if self.lit and self.w >= 0.20 * N2_100:
            self.fuel_on = True
        if self.fuel_on:
            ramp = np.clip((self.w - 0.20 * N2_100) / ((self.idle - 0.20) * N2_100), 0.0, 1.0)
            torque += self.t_comb * ramp
        self.w = max(self.w + DT * torque / self.i_hp, 0.0)
        if self.fuel_on and self.w >= self.idle * N2_100:
            self.w = self.idle * N2_100
        return self.w

    def shutdown(self) -> None:
        self.fuel_on = False
        self.lit = False


def ground_inputs(w: float, t_amb: float, p_amb: float, *, gen_load: bool = False) -> dict[str, np.ndarray]:
    """One tick of ground inputs with the engine fixture speed ``w`` (rad/s)."""
    rho = p_amb / (287.05287 * t_amb)
    return {
        "n2": np.array([[w]]),
        "bleed_p3": np.array([[p_amb * (1.0 + 2.0 * (w / N2_100) ** 2)]]),
        "bleed_t3": np.array([[t_amb * (1.0 + 0.6 * (w / N2_100) ** 2)]]),
        "wf": np.array([[0.09 if w > 0.5 * N2_100 else 0.0]]),
        "wf_ab": np.zeros((1, 1)),
        "hyd_flow_demand": np.zeros((1, 2)),
        "f_spec_body": np.array([[0.0, 0.0, -G0]]),
        "tas": np.zeros(1),
        "mach": np.zeros(1),
        "wow": np.ones((1, 3), dtype=np.int64),
        "wheel_speed": np.zeros((1, 2)),
        "brake_energy_rate": np.zeros((1, 2)),
        "t_s": np.array([t_amb]),
        "p_s": np.array([p_amb]),
        "rho": np.array([rho]),
        "w_hyd": np.zeros((1, 2)),
        "w_bleed_pto": np.zeros((1, 1)),
        "health_utility": np.zeros((1, L.N_HEALTH)),
    }


@dataclass
class StartResult:
    outcomes: list[int]
    times: list[float]  # s from start command to the outcome
    consecutive: int
    soc: list[float]  # battery SOC at each start command


def start_protocol(
    *,
    variant: int,
    t_amb: float,
    alt: float,
    soc: float,
    n_starts: int = 3,
    interval: float = 120.0,
    run_after_idle: float = 20.0,
    dry_last: bool = False,
    params: ParamSet | None = None,
    health: np.ndarray | None = None,
    root: int = 0x5EED,
) -> StartResult:
    """TEST FIXTURE protocol for the three-consecutive-start requirement (CAG 17/2015: two engine starts and a
    dry rollover, on the aircraft battery without ground power): start commands every ``interval`` s; a lit
    engine runs ``run_after_idle`` s at idle (generator online, battery charging) and is shut down."""
    ps = params if params is not None else load_m09_params()
    _, p_amb, _ = isa(alt)
    cfg = UtilitiesConfig(
        soak_temp=t_amb, p_amb=p_amb, batt_soc=soc, jfs_variant=variant, engine_running=False
    )
    m = bind(Utilities("util", ps, config=cfg), root=root)
    st = m.init(ps, None)
    w_floor = float(ps.value("jfs_w_floor"))
    hv = None if health is None else np.asarray(health)
    eng = EngineStartFixture(lit=True)
    out = StartResult([], [], 0, [])
    k = 0
    starts = 0
    t_cmd = 0.0
    t_idle = None
    pto = 0.0
    while True:
        tnow = k * DT
        mode = int(st["i"][L.I_JFS_MODE])
        if starts < n_starts and mode == 0 and tnow >= starts * interval and eng.w < 0.02 * N2_100:
            eng = EngineStartFixture(lit=not (dry_last and starts == n_starts - 1))
            st, _ = m.on_event(st, event("util.jfs_start"), 0)
            out.soc.append(float(st["f"][L.F_BATT_SOC]))
            starts += 1
            t_cmd = tnow
            t_idle = None
        done = int(st["i"][L.I_JFS_OK]) + int(st["i"][L.I_JFS_FAIL])
        inp = ground_inputs(eng.w, t_amb, p_amb)
        if hv is not None:
            inp["health_utility"] = hv[None, :]
        st, o = m.step_block(st, inp, np.array([k], np.int64), DT)
        pto = float(o["pto_power"][0, 0])
        eng.advance(pto, w_floor)
        if int(st["i"][L.I_JFS_OK]) + int(st["i"][L.I_JFS_FAIL]) > done:
            out.outcomes.append(int(st["i"][L.I_JFS_OUTCOME]))
            out.times.append(tnow - t_cmd)
            if int(st["i"][L.I_JFS_OUTCOME]) != 1:
                eng.shutdown()
        if eng.fuel_on and t_idle is None and eng.w >= eng.idle * N2_100:
            t_idle = tnow
        if t_idle is not None and tnow - t_idle > run_after_idle:
            eng.shutdown()
            t_idle = None
        k += 1
        if starts >= n_starts and len(out.outcomes) >= n_starts and int(st["i"][L.I_JFS_MODE]) == 0:
            break
        if k > int(240 * (n_starts * interval + 300)):
            raise AssertionError("start protocol did not finish")
    out.consecutive = int(st["i"][L.I_JFS_CONSEC])
    return out


# ------------------------------------------------------------------------------------------------ System
# fixture
class ScriptedUtilityInputs(ModuleBase):
    """TEST FIXTURE: emits every M09 input port from a scripted, deterministic profile (no RNG).

    Profile (period 120 s): N2 oscillates between 75 % and 97 %, bleed conditions follow N2, FCS hydraulic
    demand bursts, a pitch/acceleration cycle drives the fuel surface. Stands in for M03/M05/M06/M07/M10.
    """

    version = "1.0.0"
    rate = RG_240
    state_schema = StateSchema("test.util_inputs", 1, ())

    def __init__(self, id: str = "src", n_engines: int = 1) -> None:
        ins, _outs, _bindings = ports(n_engines)
        self.ports_out = tuple(Port(p.name, p.unit, p.dtype, p.shape) for p in ins)
        super().__init__(id, ParamSet("test.util_inputs", {}))
        self.ne = n_engines

    def init(self, params, keys):
        return {}

    def _profile(self, t: np.ndarray) -> dict[str, np.ndarray]:
        n = t.size
        s = (t.astype(np.float64) / 1e9) % 120.0
        n2f = 0.86 + 0.11 * np.sin(2 * np.pi * s / 120.0)
        p3 = 2.8e5 + (6.4e5 - 2.8e5) * np.clip((n2f - 0.75) / 0.22, 0, 1)
        t3 = 448.15 + (713.15 - 448.15) * np.clip((n2f - 0.75) / 0.22, 0, 1)
        demand = 4e-4 * (np.sin(2 * np.pi * s / 7.0) > 0.6)
        theta = 0.3 * np.sin(2 * np.pi * s / 60.0)
        fx = G0 * np.sin(theta) + 2.0 * np.cos(2 * np.pi * s / 30.0)
        fz = -G0 * np.cos(theta)
        inp = inputs(n, ne=self.ne, n2f=n2f, p3=p3, t3=t3, wf=0.3 + 0.6 * n2f, demand=demand, alt=4000.0)
        inp["f_spec_body"] = np.stack([fx, np.zeros(n), fz], axis=1)
        return inp

    def initial_outputs(self, state):
        return {k: v[0] for k, v in self._profile(np.array([0], np.int64)).items()}

    def step_block(self, state, inputs_, t, dt):
        return {}, self._profile(t)

    def step(self, state, inputs_, t, dt):
        return {}, {k: v[0] for k, v in self._profile(np.array([t], np.int64)).items()}


def utility_system(
    *,
    compiled: bool = True,
    validate: bool = False,
    block_len: int = 1024,
    root: int = 0xA14,
    config: UtilitiesConfig | None = None,
    sortie: int = 1,
    ledger=None,
) -> System:
    src = ScriptedUtilityInputs("src")
    util = Utilities("util", load_m09_params(), config=config, compiled=compiled)
    conns = [Connection(f"src.{p.name}", f"util.{p.name}") for p in util.ports_in]
    reg = StreamRegistry(util.streams)
    return System(
        [src, util],
        conns,
        rng=RngService(root, reg, ledger=ledger),
        identity=KeyPath.of(scenario="w14", tail="T1", sortie=sortie),
        block_len=block_len,
        validate=validate,
        purity_check=validate,
    )


@pytest.mark.unit
def test_fixture_isa_and_inputs_are_consistent():
    t, p, rho = isa(0.0)
    assert t == 288.15 and abs(p - 101325.0) < 1e-6 and abs(rho - 1.2250) < 1e-3
    inp = inputs(5, n2f=np.linspace(0.6, 1.0, 5))
    assert inp["n2"].shape == (5, 1) and inp["wow"].dtype == np.int64
    assert np.allclose(inp["n2"][:, 0] / N2_100, np.linspace(0.6, 1.0, 5))
