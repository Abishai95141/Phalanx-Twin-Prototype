"""A7: the documented coupling API (`phalanx.fadec.coupling`) plugs M08 into a truth loop without M08 changes.

- The scheduler wiring (catalogue ports, lane back-edges) reproduces the fused fixture loop bitwise, in step
  and block mode, and with the NumPy reference kernel.
- A second, structurally different TEST FIXTURE plant (separate SI ports, exact exponential discretisation,
  its own lane source) is governed by the same unmodified `Fadec` - the stand-in for the real M07 (W1.3a).
- The real M13 `LaneAcquisition` (W1.6) lane ports resolve through `fadec_input_connections` with identical
  unit, shape and clock domain (all of them since W2.2 made ENG.AB_LIT an M13 lane).
- The lane-source frame convention (`lane_frames`) equals M08's own schedule (`Fadec.frame_schedule`) on the
  shared offset clock and on a 67 Hz clock.
- Fault events reach the BIT consumer (M14 role) with codes matching the fault-bit transitions.

Sample sizes: 5 s (1,200 truth steps) per wiring comparison, 1 s for the reference kernel (pure Python), 20 s
for the second plant; deterministic (the only randomness is one keyed disturbance stream).
"""

from __future__ import annotations

import itertools
from typing import ClassVar

import numpy as np
import pytest

import fadec_fixture as fx
from phalanx.core.events import Event
from phalanx.core.module import ModuleBase, Param, ParamSet, Port
from phalanx.core.rng import KeyPath, RngService, StreamRegistry
from phalanx.core.sampling import samples_for_steps
from phalanx.core.scheduler import Connection, System
from phalanx.core.state import Field, StateSchema
from phalanx.core.time import ClockDomain, latest_truth_step, truth_interp_weights, truth_step_times_ns
from phalanx.fadec import Fadec
from phalanx.fadec.codes import FAULT_BY_BIT, N_FAULT_BITS, code_word
from phalanx.fadec.coupling import (
    LANE_EDGE_NOTE,
    command_connections,
    fadec_input_connections,
    lane_frames,
    lane_port_name,
)
from phalanx.fadec.layout import F_N2C_DEM, O_SEL
from phalanx.fadec.ports import DEFAULT_CLOCK, LANE_PORTS, P0_AIR_DATA, P0_ENV, RECORDED, lane_shape

pytestmark = pytest.mark.integration
ID = KeyPath.of(scenario="w13b", tail="T1", sortie=1)


def _scenario(n, *, fault_at=None):
    pla = np.full((n, 1), 60.0)
    pla[n // 2 :, 0] = 66.0
    w = np.zeros((n, 1, 4))
    w[:, 0, 3] = fx.ar1_disturbance(n, 1.0, 0.01, sortie=7, channel=3)
    fm = fv = None
    if fault_at is not None:  # N2 lane A reads high (saturates at its 110 % span top) for 1 s, then heals
        fm = np.zeros((n, 1, 12), np.int64)
        fv = np.zeros((n, 1, 12))
        fm[fault_at : fault_at + 240, 0, 2] = 1
        fv[fault_at : fault_at + 240, 0, 2] = 1.25 * 16810 * 2 * np.pi / 60
    return fx.Scenario(n, 1, pla_deg=pla, w=w, force_mask=fm, force_val=fv)


def _fadec(x0, **kw):
    return Fadec(
        "fadec",
        fx.fixture_params(),
        initial_wf=x0[:, fx.X_WF],
        initial_a8=x0[:, fx.X_A8],
        initial_vg=np.stack([x0[:, fx.X_FVG], x0[:, fx.X_CVG]], 1),
        p0_source=P0_ENV,  # TEST FIXTURE loop without the avionics module: P0 from env.p_s
        **kw,
    )


class EventLog(ModuleBase):
    """TEST FIXTURE BIT consumer (M14 role): counts set/clear events per fault bit."""

    version = "0.0.0"
    rate = None

    def __init__(self, id):
        self.state_schema = StateSchema(
            "fixture.eventlog",
            1,
            (Field("set", "<i8", (N_FAULT_BITS,)), Field("clr", "<i8", (N_FAULT_BITS,))),
        )
        super().__init__(
            id, ParamSet("fixture.eventlog", {"v": Param(1.0, "1", "ASSUMPTION", fx.FIXTURE_SOURCE)})
        )
        self.bit_of = {f.code: f.bit for f in FAULT_BY_BIT.values()}

    def init(self, params, keys):
        z = np.zeros(N_FAULT_BITS, np.int64)
        return {"set": z.copy(), "clr": z.copy()}

    def initial_outputs(self, state):
        return {}

    def on_event(self, state, event: Event, t):
        b = self.bit_of[str(event.payload["code"])]
        key = "set" if bool(event.payload["set"]) else "clr"
        new = {k: v.copy() for k, v in state.items()}
        new[key][b] += 1
        return new, []


def _system(sc, x0, *, compiled=True, events=False):
    fad = _fadec(x0, compiled=compiled, event_target="bit" if events else None)
    scen = fx.FixtureScenario("scen", sc, fx.capacity(fad.clock))
    plant = fx.FixturePlant("plant", x0)
    lanes = fx.FixtureLanes("lanes", fad.clock, 1, sc)
    conns = fadec_input_connections("fadec", fad.bindings, {"pilot": "scen", "env": "scen"}, "lanes")
    conns = [Connection(c.src.replace("scen.p_s", "scen.p0"), c.dst, c.delayed, c.note) for c in conns]
    conns += command_connections("fadec", "plant", plant.bindings)
    conns += [
        Connection("scen.t_amb", "plant.t_amb"),
        Connection("scen.p0", "plant.p_amb"),
        Connection("scen.mach", "plant.mach"),
        Connection("scen.ex", "plant.ex"),
        Connection("plant.x", "lanes.x_now"),
        Connection("plant.x", "lanes.x_prev", True, "x_k for interpolation"),
    ]
    mods = [scen, fad, plant, lanes] + ([EventLog("bit")] if events else [])
    return System(mods, conns, rng=RngService(1, StreamRegistry()), identity=ID)


@pytest.mark.parametrize("mode", ["step", "block"])
def test_scheduler_wiring_reproduces_the_fused_loop_bitwise(mode):
    n = 5 * 240
    sc = _scenario(n)
    x0 = fx.steady_state(60.0)
    syst = _system(sc, x0)
    rec = ["plant.x", "fadec.wf_cmd", "fadec.active_limiter", "fadec.n2_v", "fadec.fault_code"]
    _, tr = syst.run(syst.start(), n, mode=mode, record=rec)
    r = fx.closed_loop(sc, x0=x0)
    assert np.array_equal(tr.ports["plant.x"], r.xs[1:])
    assert np.array_equal(tr.ports["fadec.wf_cmd"], r.wf_cmd)
    assert np.array_equal(tr.ports["fadec.active_limiter"], r.limiter)
    assert np.array_equal(tr.ports["fadec.n2_v"], r.cmdf[:, :, O_SEL + 1])  # recorded = the law's selection


def test_reference_kernel_module_matches_the_compiled_module_bitwise():
    n = 240
    sc = _scenario(n)
    x0 = fx.steady_state(60.0)
    out = []
    for compiled in (True, False):
        syst = _system(sc, x0, compiled=compiled)
        _, tr = syst.run(syst.start(), n, mode="block", record=["plant.x", "fadec.wf_cmd", "fadec.t5_avg"])
        out.append(tr.ports)
    for k in out[0]:
        assert np.array_equal(out[0][k], out[1][k]), k


@pytest.mark.parametrize("mode", ["step", "block"])
def test_fault_events_reach_the_bit_consumer_matching_the_fault_bit_transitions(mode):
    """Per-step and block execution (W2.1b: M08 opts into block-mode events, `step_block_emits_events`) give
    the same events at the consumer."""
    n = 5 * 240
    sc = _scenario(n + 1, fault_at=480)  # one extra scenario row: the drain step below
    x0 = fx.steady_state(60.0)
    syst = _system(sc, x0, events=True)
    w, tr = syst.run(syst.start(), n, mode=mode, record=["fadec.fault_code"])
    r = fx.closed_loop(sc, x0=x0)
    masks = np.concatenate([[0], r.faults[:n, 0]]).astype(np.int64)
    want_set = np.zeros(N_FAULT_BITS, np.int64)
    want_clr = np.zeros(N_FAULT_BITS, np.int64)
    for a, b in itertools.pairwise(masks):
        for bit in FAULT_BY_BIT:
            was, now = (a >> bit) & 1, (b >> bit) & 1
            want_set[bit] += int(now and not was)
            want_clr[bit] += int(was and not now)
    # events emitted at the last step are dispatched at the next step: run one more step to drain the queue
    w, _ = syst.run(w, 1, mode=mode)
    st = w.states["bit"]
    # the saturated lane passes its range check; the lanes disagree -> cross-channel soft-fail (ENG-032), the
    # safer (higher) N2 is selected, which reads as an N2 overspeed exceedance (ENG-703); both clear on heal
    assert want_set[13] == 1 and want_clr[13] == 1
    assert np.array_equal(st["set"], want_set) and np.array_equal(st["clr"], want_clr)
    assert np.array_equal(tr.ports["fadec.fault_code"][:, 0], code_word(r.faults[:n, 0]))
    assert 703 in set(tr.ports["fadec.fault_code"][:, 0])


def test_real_m13_lane_ports_resolve_through_the_coupling_api():
    from phalanx.acquisition.ports import lane_modules

    m13 = lane_modules(1)["FADEC"]
    out = {p.name: p for p in m13.ports_out}
    fad = Fadec("fadec", fx.fixture_params())
    ins = {p.name: p for p in fad.ports_in}
    # the Tejas bindings: P0 from the avionics ADC's static pressure (W2.2)
    conns = fadec_input_connections("fadec", fad.bindings, {"pilot": "m04", "avio": "avio"}, m13.id)
    assert Connection(f"avio.{P0_AIR_DATA.split('.', 1)[1]}", "fadec.p0") in conns
    lane_conns = [c for c in conns if c.src.startswith(f"{m13.id}.")]
    assert len(lane_conns) == len(LANE_PORTS)
    unresolved = []
    for c in lane_conns:
        assert c.delayed and c.note == LANE_EDGE_NOTE
        src = c.src.split(".", 1)[1]
        if src not in out:
            unresolved.append(src)
            continue
        p, q = ins[c.dst.split(".", 1)[1]], out[src]
        assert (p.unit, p.dtype, p.shape, p.rate) == (q.unit, q.dtype, q.shape, q.rate), src
    assert unresolved == []  # ENG.AB_LIT included (W2.2: the M12 UV flame detector lane)
    assert fad.clock == DEFAULT_CLOCK and all(p.rate == DEFAULT_CLOCK for p in fad.ports_out)
    assert set(RECORDED) <= {p.name for p in fad.ports_out}


@pytest.mark.parametrize(
    "clock",
    [DEFAULT_CLOCK, ClockDomain("FADEC", 67, offset_ppm=900, phase_ns=7_000_000)],
    ids=["m13", "67Hz"],
)
def test_lane_source_frames_equal_the_fadec_frame_schedule(clock):
    fad = Fadec("fadec", fx.fixture_params(), clock=clock)
    st = fad.init(fad.params, None)
    n_src = clock.first_index_at_or_after(0)
    for k in range(600):
        ss, w = lane_frames(clock, n_src, k)
        n_src = ss.next_index
        sched = fad.frame_schedule(st, truth_step_times_ns(np.array([k + 1])))
        assert np.array_equal(ss.times, sched.times) and ss.first == sched.first
        st["g"][0] = sched.next_index
        assert w.shape == ss.times.shape and np.all((w >= 0) & (w <= 1))


# ------------------------------------------------------------------ a structurally different plant
class LinearPlant(ModuleBase):
    """TEST FIXTURE (second plant): separate SI output ports, exact exponential discretisation of first-order
    spool/pressure/temperature lags, fuel-metering valve; uses the fixture's steady maps for magnitudes. No
    VG, nozzle or AB effects. Declares the catalogue command bindings exactly as the real M07 will."""

    version = "0.0.0"
    rate = fx.RG_240
    OUT = (("n1", "rad/s"), ("n2", "rad/s"), ("t1", "K"), ("t25", "K"), ("ps3", "Pa"), ("t5", "K"))

    def __init__(self, id, n2c0, *, t2=288.15, p2=101325.0):
        self.ports_in = (
            Port("wf_cmd", "kg/s", "<f8", (1,)),
            Port("wf_ab_cmd", "kg/s", "<f8", (1,)),
            Port("a8_cmd", "m**2", "<f8", (1,)),
            Port("vg_cmd", "rad", "<f8", (1, 2)),
            Port("ignition", "1", "<i8", (1,)),
            Port("ab_enable", "1", "<i8", (1,)),
        )
        self.bindings = {p.name: f"fadec.{p.name}" for p in self.ports_in}
        self.ports_out = tuple(Port(n, u, "<f8", (1,)) for n, u in self.OUT)
        self.state_schema = StateSchema(
            "fixture.linear", 1, (Field("n2c", "<f8", ()), Field("wf", "<f8", ()))
        )
        super().__init__(
            id, ParamSet("fixture.linear", {"v": Param(1.0, "1", "ASSUMPTION", fx.FIXTURE_SOURCE)})
        )
        self.pt, self.pp = fx.plant_tables(), fx.plant_params()
        self.t2, self.p2, self.n2c0 = t2, p2, n2c0

    def _wf_of(self, n2c):
        return (
            float(np.interp(n2c, self.pt.wf_x, self.pt.wf_y))
            * 1.15
            * (self.p2 / 101325.0)
            * np.sqrt(self.t2 / 288.15)
        )

    def init(self, params, keys):
        return {"n2c": np.array(self.n2c0), "wf": np.array(self._wf_of(self.n2c0))}

    def _outputs(self, n2c):
        pt, sth = self.pt, np.sqrt(self.t2 / 288.15)
        n1c = float(np.interp(n2c, pt.n1_x, pt.n1_y))
        return {
            "n1": np.array([n1c * sth * 13270 * 2 * np.pi / 60]),
            "n2": np.array([n2c * sth * 16810 * 2 * np.pi / 60]),
            "t1": np.array([self.t2]),
            "t25": np.array([self.t2 * float(np.interp(n1c, pt.t25_x, pt.t25_y))]),
            "ps3": np.array([self.p2 * float(np.interp(n2c, pt.pr_x, pt.pr_y))]),
            "t5": np.array([self.t2 * float(np.interp(n2c, pt.t5_x, pt.t5_y))]),
        }

    def initial_outputs(self, state):
        return self._outputs(float(state["n2c"]))

    def step(self, state, inputs, t, dt):
        a_v = np.exp(-dt / 0.06)
        wf = a_v * float(state["wf"]) + (1 - a_v) * float(inputs["wf_cmd"][0])
        wfc = wf / (1.15 * (self.p2 / 101325.0) * np.sqrt(self.t2 / 288.15))
        n2ss = float(np.interp(wfc, self.pt.n2_x, self.pt.n2_y))
        a = np.exp(-dt / 1.5)
        n2c = a * float(state["n2c"]) + (1 - a) * n2ss
        return {"n2c": np.array(n2c), "wf": np.array(wf)}, self._outputs(n2c)


class LinearLanes(ModuleBase):
    """TEST FIXTURE lane source for `LinearPlant`: M13 port names and shapes, linear interpolation between
    the delayed (x_k) and current (x_{k+1}) plant outputs at the FADEC frame instants, no quantisation."""

    version = "0.0.0"
    rate = fx.RG_240
    SRC: ClassVar[dict[str, tuple[str, ...]]] = {
        "n1": ("n1_a", "n1_b"),
        "n2": ("n2_a", "n2_b"),
        "t1": ("t1_a", "t1_b"),
        "t25": ("t25",),
        "ps3": ("ps3_a", "ps3_b"),
        "t5": ("t5_a", "t5_b"),
    }

    def __init__(self, id, clock):
        self.clock, self.shape = clock, lane_shape(1, clock)
        names = [n for n, _ in LinearPlant.OUT]
        units = dict(LinearPlant.OUT)
        self.ports_in = tuple(Port(f"{n}_now", units[n], "<f8", (1,)) for n in names) + tuple(
            Port(f"{n}_prev", units[n], "<f8", (1,)) for n in names
        )
        self.port_of = {name: lane_port_name(cid) for name, cid, _u in LANE_PORTS}
        self.ports_out = tuple(
            Port(self.port_of[nm], u, "<f8", self.shape, clock) for nm, _c, u in LANE_PORTS
        )
        self.state_schema = StateSchema("fixture.linlanes", 1, (Field("n_next", "<i8", ()),))
        super().__init__(
            id, ParamSet("fixture.linlanes", {"v": Param(1.0, "1", "ASSUMPTION", fx.FIXTURE_SOURCE)})
        )

    def init(self, params, keys):
        return {"n_next": np.array(self.clock.first_index_at_or_after(0), dtype=np.int64)}

    def initial_outputs(self, state):
        return {p.name: np.zeros(self.shape) for p in self.ports_out}

    def step(self, state, inputs, t, dt):
        k = latest_truth_step(int(t))
        t0, t1 = truth_step_times_ns(np.array([k, k + 1], dtype=np.int64))
        ss = samples_for_steps(self.clock, int(state["n_next"]), np.array([t0]), np.array([t1]))
        out = {p.name: np.zeros(self.shape) for p in self.ports_out}
        if ss.times.size:
            _, w = truth_interp_weights(ss.times)
            for src, lanes in self.SRC.items():
                a, b = float(inputs[f"{src}_prev"][0]), float(inputs[f"{src}_now"][0])
                for slot, wi in enumerate(w):
                    for ln in lanes:
                        out[self.port_of[ln]][slot] = a + wi * (b - a)
        return {"n_next": np.array(ss.next_index, dtype=np.int64)}, out


def test_a_structurally_different_plant_is_governed_by_the_unchanged_fadec():
    n = 20 * 240
    pla = np.full((n, 1), 50.0)
    pla[n // 4 :, 0] = 65.0
    sc = fx.Scenario(n, 1, pla_deg=pla)
    plant = LinearPlant("eng", 0.80)
    st0 = plant.init(None, None)
    # TEST FIXTURE loop without the avionics module: P0 from env.p_s
    fad = Fadec("fadec", fx.fixture_params(), initial_wf=[float(st0["wf"])], p0_source=P0_ENV)
    scen = fx.FixtureScenario("scen", sc, fx.capacity(fad.clock))
    lanes = LinearLanes("lanes", fad.clock)
    conns = fadec_input_connections("fadec", fad.bindings, {"pilot": "scen", "env": "scen"}, "lanes")
    conns = [Connection(c.src.replace("scen.p_s", "scen.p0"), c.dst, c.delayed, c.note) for c in conns]
    conns += command_connections("fadec", "eng", plant.bindings)
    for name, _u in LinearPlant.OUT:
        conns += [
            Connection(f"eng.{name}", f"lanes.{name}_now"),
            Connection(f"eng.{name}", f"lanes.{name}_prev", True, "x_k for interpolation"),
        ]
    syst = System([scen, fad, plant, lanes], conns, rng=RngService(1, StreamRegistry()), identity=ID)
    w, tr = syst.run(syst.start(), n, mode="block", record=["eng.n2", "eng.t25", "fadec.active_limiter"])
    n2 = tr.ports["eng.n2"][:, 0] / (16810 * 2 * np.pi / 60)
    n2c25 = n2 / np.sqrt(tr.ports["eng.t25"][:, 0] / 288.15)
    dem = float(w.states["fadec"]["f"][0, F_N2C_DEM])
    assert (tr.ports["fadec.active_limiter"][-240:, 0] & 15 == 1).all()  # N2 governor in control
    assert abs(n2c25[-1] - dem) < 0.005  # settles on the PLA-65 demand
    assert n2c25[-1] > n2c25[n // 4 - 1] + 0.01  # and moved there from the PLA-50 point
