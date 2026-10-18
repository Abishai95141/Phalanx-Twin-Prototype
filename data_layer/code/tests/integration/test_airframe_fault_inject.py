"""AD-48.4 (W2.1c): ``af.fault_inject`` is a ground-model state perturbation in M06 (I6), per gear leg.

Each catalogued airframe mode moves the physics the way its mechanism says (A-W2.1c-2 values, swept in
M06.yaml): a burst main tyre drops its side by r_roll - rim_radius and drags (rim rolling coefficient); an
ice-locked strut stays compressed and stiff; a collapsed gear leg lets its side settle onto the structure; a
runway excursion adds soft-ground rolling resistance; ``clear`` restores the healthy leg. Unknown modes, bad
legs and another tail's events are rejected / ignored.

Deterministic kernel runs on a level runway (``test_airframe_ground.Ground``): 5 s settle at rest for the
attitude and height cases, 3 s free roll from 20 m/s for the drag cases (n = 1 run per case; 9 cases).
"""

from __future__ import annotations

import numpy as np
import pytest
from test_airframe_ground import CG, LAT, LON, PS, Ground, J, M

from phalanx.airframe.analysis import input_row
from phalanx.airframe.geodesy import euler_to_quat, quat_to_euler
from phalanx.airframe.ic import AirframeIC
from phalanx.airframe.kernel import AF_FAULT_MODES, F_FLT0, O_HAG, O_NZ, O_QN0, O_VN, O_WOW0
from phalanx.airframe.module import Airframe
from phalanx.core.events import Event
from phalanx.core.module import ContractError
from phalanx.health.protocol import plain_payload

pytestmark = pytest.mark.integration
NOSE, LEFT, RIGHT, ALL = 0, 1, 2, -1


def _module() -> Airframe:
    u = input_row(1, np.zeros(13), 0.0, M, CG, J, 0.0, gear_cmd=1)
    ic = AirframeIC(LAT, LON, 1.75, (0.0, 0.0, 0.0), tuple(euler_to_quat(0.0, 0.0, 0.0)), u, gear=1.0)
    return Airframe.from_registry("af", ic)


AF = _module()


def inject(f: np.ndarray, mode: str, leg: int, param: float = 1.0, *, clear=False, tail="T") -> np.ndarray:
    """The M06 handler applied to a float state (the event M11 sends, plain keys)."""
    doc = {"tail": tail, "mode": mode, "param": param, "instance": 0, "engine": 0, "clear": clear, "leg": leg}
    st = {"f": f.copy(), "i": np.zeros(2, np.int64)}
    new, out = AF.on_event(st, Event(0, "af.fault_inject", "af", plain_payload(doc), source="m11"), 0)
    assert out == []
    return new["f"]


def _settled(modes=(), v=0.0, n=1200):
    g = Ground(v=v)
    for mode, leg, param in modes:
        g.f = inject(g.f, mode, leg, param)
    out = g.run(n)
    phi, _theta, _psi = quat_to_euler(out[-1, O_QN0 : O_QN0 + 4])
    return out, float(phi), float(out[-1, O_HAG])


HEALTHY = _settled()


def test_handler_sets_and_clears_per_leg_severity():
    f0 = Ground().f
    f1 = inject(f0, "tyre_burst", LEFT, 0.6)
    k = F_FLT0 + 3 * AF_FAULT_MODES.index("tyre_burst")
    assert f1[k + LEFT] == 0.6 and f1[k + NOSE] == 0.0 and f1[k + RIGHT] == 0.0
    f2 = inject(f1, "runway_excursion", ALL, 3.0)  # severity clipped to 1
    s = F_FLT0 + 3 * AF_FAULT_MODES.index("runway_excursion")
    assert np.all(f2[s : s + 3] == 1.0)
    f3 = inject(f2, "tyre_burst", LEFT, clear=True)
    assert f3[k + LEFT] == 0.0 and np.all(f3[s : s + 3] == 1.0)
    assert np.array_equal(np.delete(f3, range(F_FLT0, f3.size)), np.delete(f0, range(F_FLT0, f0.size)))


def test_rejects_unknown_mode_and_leg_and_ignores_another_tail():
    f0 = Ground().f
    with pytest.raises(ContractError):
        inject(f0, "wing_falls_off", LEFT)
    with pytest.raises(ContractError):
        inject(f0, "tyre_burst", 3)
    af = Airframe.from_registry("af", _ic(), identity={"tail": "T1"})
    from phalanx.core.rng import KeyPath, RngService, StreamRegistry

    af.bind(RngService(1, StreamRegistry()).scope(KeyPath.of(scenario="x")))
    st = af.init(af.params, af.keys)
    doc = {
        "tail": "OTHER",
        "mode": "tyre_burst",
        "param": 1.0,
        "instance": 0,
        "engine": 0,
        "clear": False,
        "leg": 1,
    }
    new, _ = af.on_event(st, Event(0, "af.fault_inject", "af", plain_payload(doc), source="m11"), 0)
    assert np.array_equal(new["f"], st["f"])


def _ic():
    u = input_row(1, np.zeros(13), 0.0, M, CG, J, 0.0, gear_cmd=1)
    return AirframeIC(LAT, LON, 1.75, (0.0, 0.0, 0.0), tuple(euler_to_quat(0.0, 0.0, 0.0)), u, gear=1.0)


def test_tyre_burst_drops_its_side():
    """A burst left main tyre: the aircraft settles left wing low and lower, by about half the rim drop at the
    CG (the drop is r_roll - rim_radius = 0.106 m at the left main; track 2.4 m)."""
    _, phi0, h0 = HEALTHY
    _, phi, h = _settled([("tyre_burst", LEFT, 1.0)])
    drop = float(PS.value("r_roll")) - float(PS.value("rim_radius"))
    assert phi < phi0 - 0.5 * drop / 2.4  # left wing down (roll negative)
    assert 0.2 * drop < h0 - h < 0.8 * drop


def test_strut_extension_failure_makes_the_mains_rigid():
    """Ice-locked main struts stay compressed: at rest the CG height barely changes (the frozen stroke is
    about the static stroke), but the struts no longer absorb a touchdown - dropped from 0.2 m above the
    rest height the peak load factor is clearly higher."""
    _, phi0, h0 = HEALTHY
    _, phi, h = _settled([("strut_extension_failure", LEFT, 1.0), ("strut_extension_failure", RIGHT, 1.0)])
    assert abs(h0 - h) < 0.05 and abs(phi - phi0) < 1e-3  # symmetric, near the healthy rest height

    def peak_nz(modes):
        g = Ground(h=h0 + 0.2)
        for mode, leg, param in modes:
            g.f = inject(g.f, mode, leg, param)
        return float(g.run(480)[:, O_NZ].max())

    frozen = [("strut_extension_failure", LEFT, 1.0), ("strut_extension_failure", RIGHT, 1.0)]
    assert peak_nz(frozen) > 1.3 * peak_nz([])


def test_gear_collapse_settles_its_side_onto_the_structure():
    out, phi, h = _settled([("gear_collapse_on_touchdown", RIGHT, 1.0)])
    _, phi0, h0 = HEALTHY
    assert phi > phi0 + 0.05 and h0 - h > 0.3  # right wing down, far lower
    assert out[-1, O_WOW0 + RIGHT] == 1.0  # the structure is on the runway at that station


def _roll_speed(modes) -> float:
    g = Ground(v=20.0)
    for mode, leg, param in modes:
        g.f = inject(g.f, mode, leg, param)
    out = g.run(720)
    return float(np.linalg.norm(out[-1, O_VN : O_VN + 3]))


def test_runway_excursion_and_burst_tyre_add_rolling_drag():
    """3 s free roll from 20 m/s: soft ground decelerates by about mu_soft g x 3 s more than the runway; a
    burst main tyre adds its rim drag on one leg."""
    v0 = _roll_speed([])
    v_soft = _roll_speed([("runway_excursion", ALL, 1.0)])
    v_burst = _roll_speed([("tyre_burst", LEFT, 1.0)])
    mu_soft = float(PS.value("mu_soft"))
    assert v0 - v_soft == pytest.approx(mu_soft * 9.81 * 3.0, rel=0.25)
    assert v_soft < v_burst < v0


def test_clear_restores_the_healthy_leg():
    g = Ground()
    g.f = inject(g.f, "gear_collapse_on_touchdown", RIGHT, 1.0)
    g.f = inject(g.f, "gear_collapse_on_touchdown", RIGHT, clear=True)
    out = g.run(1200)
    h = HEALTHY[0]
    assert np.array_equal(out, h)  # bitwise the never-faulted run


def test_m11_downlock_fault_collapses_the_right_main_end_to_end():
    """End to end: M10's right lock-spring state triggers FM.LG.DOWNLOCK_FORCE in the real M11, whose
    af.fault_inject (leg 2) is handled by the real M06: the right side settles onto the structure."""
    from phalanx.core.module import ModuleBase, ParamSet
    from phalanx.core.rng import KeyPath, RngService, StreamRegistry
    from phalanx.core.scheduler import System
    from phalanx.dictionary import load_dictionary
    from phalanx.faults import FaultConfig, FaultInjector, load_catalogue, load_fault_params, load_graph
    from phalanx.health import sensor_bias_channels

    class Sink(ModuleBase):  # TEST FIXTURE: collects M11's airframe events for the real M06 below
        version, rate = "0", None

        def __init__(self):
            super().__init__("af", ParamSet("sink", {}))
            self.got = []

        def init(self, params, keys):
            return {}

        def on_event(self, state, event, t):
            self.got.append(event)
            return state, []

    bias = sensor_bias_channels(load_dictionary())
    cfg = FaultConfig(load_catalogue(), load_graph(), {"airframe": "af"}, ("IN20-0001",), bias)
    sink = Sink()
    m11 = FaultInjector("m11", load_fault_params(), config=cfg, identity={"tail": "T"})
    s = System([m11, sink], [], rng=RngService(3, StreamRegistry()), identity=KeyPath.of(scenario="x"))
    trig = Event(10**9, "faults.trigger", "m11", {"trigger": "util:lock_spring_r"})
    s.run(s.inject(s.start(), [trig]), 480)
    assert [e.kind for e in sink.got] == ["af.fault_inject"]
    g = Ground()
    st = {"f": g.f.copy(), "i": np.zeros(2, np.int64)}
    st, _ = AF.on_event(st, sink.got[0], 0)
    g.f = st["f"]
    _, phi0, h0 = HEALTHY
    out = g.run(1200)
    phi = float(quat_to_euler(out[-1, O_QN0 : O_QN0 + 4])[0])
    assert phi > phi0 + 0.05 and h0 - float(out[-1, O_HAG]) > 0.3
