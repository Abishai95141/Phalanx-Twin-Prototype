"""W1.3b A7 gap (W2.1 brief): the REAL `EngineModule` (M07) and the REAL `Fadec` (M08) wired in a core
`System` through `fadec_input_connections` / `command_connections`, against the fused W2.1b harness
(`tests/engine_fadec_loop.py`), bitwise.

Only the lane source and the exogenous inputs are TEST FIXTURE modules (the M12/M13 and M03/M04/M09/M10 roles,
which W2.1a wires in the integrated loop): `M07Lanes` applies the harness's M12-class sensor lags to the M07
output ports and the fixture lane quantiser at the FADEC frame instants (same njit helpers as the harness), so
the System and the fused loop compute the same thing in the same order. n = 960 steps (4 s; PLA 60 -> 80 at
1 s) per execution mode.
"""

from __future__ import annotations

import numpy as np
import pytest

import engine_fadec_loop as L
import fadec_fixture as fx
from phalanx.core.module import ModuleBase, ParamSet, Port
from phalanx.core.rng import KeyPath, RngService, StreamRegistry
from phalanx.core.scheduler import Connection, System
from phalanx.core.state import Field, StateSchema
from phalanx.core.time import RG_240, latest_truth_step
from phalanx.engine.layout import (
    AB_LIT,
    NY,
    U_MACH,
    U_NAMES,
    U_PS,
    U_Q,
    U_TS,
    Y_N1,
    Y_N2,
    Y_PS3,
    Y_T2,
    Y_T5,
    Y_T25,
    Y_W2,
)
from phalanx.engine.module import EngineModule
from phalanx.engine.ports import _FLOAT_OUTPUTS
from phalanx.engine.steady import TrimCondition
from phalanx.fadec import FadecConfig, load_fadec_params
from phalanx.fadec.coupling import command_connections, fadec_input_connections, lane_frames, lane_port_name
from phalanx.fadec.module import Fadec
from phalanx.fadec.ports import LANE_PORTS, LANE_SLOT, P0_ENV, capacity, lane_shape
from phalanx.fadec.trim import operating_point

pytestmark = pytest.mark.integration
N = 960
K_STEP = 240
COND = TrimCondition()
_Y_PORTS = (
    ("n1", Y_N1),
    ("n2", Y_N2),
    ("t2", Y_T2),
    ("t25", Y_T25),
    ("ps3", Y_PS3),
    ("t5", Y_T5),
    ("w2", Y_W2),
)


def _pla_deg():
    pla = np.full(N, 60.0)
    pla[K_STEP:] = 80.0
    return pla


class Exogenous(ModuleBase):
    """TEST FIXTURE: pilot PLA and the ambient/utility/health inputs of M07/M08 (constant condition)."""

    version = "0"
    rate = RG_240
    state_schema = StateSchema("fixture.exo", 1, ())

    def __init__(self, id: str, u: np.ndarray, pla_deg: np.ndarray):
        self.u, self.pla = u, np.deg2rad(pla_deg)
        self.ports_out = (
            Port("pla", "rad", "<f8", (1,)),
            Port("p_s", "Pa"),
            Port("t_s", "K"),
            Port("q_spec", "1"),
            Port("mach", "1"),
            Port("w_engine", "1", "<f8", (1, 5)),
            Port("bleed_extract", "kg/s", "<f8", (1,)),
            Port("pto_power", "W", "<f8", (1,)),
            Port("fuel_inlet_t", "K", "<f8", (1,)),
            Port("engine", "1", "<f8", (1, 10)),
        )
        super().__init__(id, ParamSet("fixture.exo", {}))

    def init(self, params, keys):
        return {}

    def _vals(self, k: int):
        u = self.u
        lo = U_NAMES.index("w_fuel_metering")
        return {
            "pla": np.array([self.pla[min(k, N - 1)]]),
            "p_s": np.array(u[U_PS]),
            "t_s": np.array(u[U_TS]),
            "q_spec": np.array(u[U_Q]),
            "mach": np.array(u[U_MACH]),
            "w_engine": u[lo : lo + 5].reshape(1, 5).copy(),
            "bleed_extract": np.array([u[U_NAMES.index("bleed_extract")]]),
            "pto_power": np.array([u[U_NAMES.index("pto_power")]]),
            "fuel_inlet_t": np.array([u[U_NAMES.index("t_fuel")]]),
            "engine": u[U_NAMES.index("h_fan_eta") : U_NAMES.index("h_fan_eta") + 10].reshape(1, 10).copy(),
        }

    def initial_outputs(self, state):
        return self._vals(0)

    def step(self, state, inputs, t, dt):
        return {}, self._vals(latest_truth_step(int(t)))


class M07Lanes(ModuleBase):
    """TEST FIXTURE lane source on the M07 output ports (the harness's sensor lags + fixture quantiser)."""

    version = "0"
    rate = RG_240

    def __init__(self, id: str, clock, y0: np.ndarray, yi0: np.ndarray):
        self.clock, self.cap = clock, capacity(clock)
        self.shape = lane_shape(1, clock)
        self.names = {name: lane_port_name(cid) for name, cid, _u in LANE_PORTS}
        unit = dict(_FLOAT_OUTPUTS)  # M07's port units
        self.ports_in = (
            *(Port(n, unit[n], "<f8", (1,)) for n, _ in _Y_PORTS),
            Port("ab_state", "1", "<i8", (1,)),
        )
        self.ports_out = tuple(Port(self.names[n], u, "<f8", self.shape, clock) for n, _c, u in LANE_PORTS)
        self.state_schema = StateSchema(
            "fixture.m07_lanes", 1,
            (Field("n_next", "<i8", ()), Field("lag", "<f8", (L.NS_LAG,)), Field("q0", "<f8", (L.NS_LAG,)),
             Field("xprev", "<f8", (fx.NX,))),
        )  # fmt: skip
        super().__init__(id, ParamSet("fixture.m07_lanes", {}))
        self.y0, self.yi0 = y0, yi0
        self.lp = L.m12_lag_params()
        self.q = fx.lane_quantiser()

    def init(self, params, keys):
        tr = L._truth_row(self.y0, 0.0)
        lit = 1.0 if self.yi0[0] == AB_LIT else 0.0
        return {
            "n_next": np.array(self.clock.first_index_at_or_after(0), dtype=np.int64),
            "lag": tr.copy(),
            "q0": tr.copy(),
            "xprev": L._sensor_vec(self.y0, tr, lit),
        }

    def initial_outputs(self, state):
        return {self.names[n]: np.zeros(self.shape) for n, _c, _u in LANE_PORTS}

    def step(self, state, inputs, t, dt):
        k = latest_truth_step(int(t))
        y = np.zeros(NY)
        for name, j in _Y_PORTS:
            y[j] = float(inputs[name][0])
        tr = L._truth_row(y, 0.0)
        lag, q0 = state["lag"].copy(), state["q0"].copy()
        for s in range(L.NS_LAG):
            lag[s] = L._foh(lag[s], q0[s], tr[s], L._tau(self.lp, s, y[Y_W2]), L.DT)
            q0[s] = tr[s]
        lit = 1.0 if int(inputs["ab_state"][0]) == AB_LIT else 0.0
        xnew = L._sensor_vec(y, lag, lit)
        ss, w = lane_frames(self.clock, int(state["n_next"]), k)
        out = {n: np.zeros(self.cap) for n, _c, _u in LANE_PORTS}
        zz, zi = np.zeros(12), np.zeros(12, dtype=np.int64)
        for slot in range(ss.times.size):
            v = fx.lane_values(state["xprev"], xnew, float(w[slot]), *self.q, zz, zz, zi, zz)
            v[12] = xnew[fx.X_ABLIT]
            for n, _c, _u in LANE_PORTS:
                out[n][slot] = v[LANE_SLOT[n]]
        new = {"n_next": np.array(ss.next_index, dtype=np.int64), "lag": lag, "q0": q0, "xprev": xnew}
        return new, {self.names[n]: v.reshape(self.shape) for n, v in out.items()}


@pytest.fixture(scope="module")
def setup():
    cfg = FadecConfig.build(load_fadec_params())
    eng0 = EngineModule("eng")
    op = operating_point(eng0.model, cfg, 60.0, COND)
    return cfg, eng0, op


def _system(cfg, eng0, op):
    eng = eng0.from_trim(op.engine)
    st0 = eng.init(eng.params, None)
    # TEST FIXTURE loop without the avionics module: P0 from env.p_s
    fad = Fadec("fadec", load_fadec_params(), p0_source=P0_ENV, **L.fadec_kwargs(cfg, op.engine))
    exo = Exogenous("exo", COND.inputs(eng.model), _pla_deg())
    lanes = M07Lanes("lanes", fad.clock, st0["y"][0], st0["yi"][0])
    producers = {"pilot": "exo", "env": "exo", "af": "exo", "util": "exo", "health": "exo"}
    conns = fadec_input_connections("fadec", fad.bindings, producers, "lanes")
    conns += command_connections("fadec", "eng", eng.bindings)
    for port, signal in eng.bindings.items():
        prefix, name = signal.split(".", 1)
        if prefix != "fadec":
            conns.append(Connection(f"{producers[prefix]}.{name}", f"eng.{port}"))
    conns += [Connection(f"eng.{n}", f"lanes.{n}") for n, _ in _Y_PORTS]
    conns.append(Connection("eng.ab_state", "lanes.ab_state"))
    return System(
        [exo, fad, eng, lanes], conns, rng=RngService(7, StreamRegistry()),
        identity=KeyPath.of(scenario="w21b", tail="T1", sortie=1),
    )  # fmt: skip


@pytest.mark.parametrize("mode", ["step", "block"])
def test_real_m07_and_m08_in_a_system_equal_the_fused_harness_bitwise(setup, mode):
    cfg, eng0, op = setup
    syst = _system(cfg, eng0, op)
    rec = ["eng.n1", "eng.n2", "eng.wf", "eng.t5", "fadec.wf_cmd", "fadec.a8_cmd", "fadec.active_limiter"]
    _, tr = syst.run(syst.start(), N, mode=mode, record=rec)
    ref = L.run(eng0, op.engine, _pla_deg(), n=N, condition=COND, cfg=cfg)
    for name in ("n1", "n2", "wf", "t5"):
        assert np.array_equal(tr.ports[f"eng.{name}"][:, 0], ref.ch(name)), name
    from phalanx.fadec.layout import O_A8, O_LIMITER, O_WF

    assert np.array_equal(tr.ports["fadec.wf_cmd"][:, 0], ref.cmdf[:, 0, O_WF])
    assert np.array_equal(tr.ports["fadec.a8_cmd"][:, 0], ref.cmdf[:, 0, O_A8])
    assert np.array_equal(tr.ports["fadec.active_limiter"][:, 0], ref.cmdi[:, 0, O_LIMITER])
    # and the loop did something: the PLA step accelerated the engine
    assert ref.ch("n2")[-1] > 1.03 * ref.ch("n2")[K_STEP - 1]
