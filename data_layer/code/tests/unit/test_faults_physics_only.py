"""W2.5 acceptance A1: every catalogue fault enters only through the physics (I6; AD-18, AD-48.4).

Each mode is injected once into a real M11 whose every effect target is a recording TEST FIXTURE (module
boundary). Everything M11 sends must be a state perturbation addressed to the module that owns the state
(M10 ``health.fault``, M12 ``sensor_fault``, M14 ``monitor.lru_condition`` = the LRU's physical condition,
M09 ``util.fault``, M05 ``fcs.*_fault``, M07/M08/M06 ``*.fault_inject``) or hidden truth for maintenance
outcomes (``truth.*``, ``ops.start_failure``): never an observation, a recorded value, a code record or a
contract topic. The recorded-data side of the same guarantee (a fault changes recorded data only where its
physics changed the acquisition input) is the paired pipeline invariance of the label-leak audit
(``analysis/faults_b7b8``; ``tests/integration/test_faults_bench_leak.py``).

Sample: every catalogue mode once, run 120 s past its onset (longer than every fixed latency and duration
that matters here); the physics mode (gauging artefact) is not injectable and is checked to be so."""

from __future__ import annotations

import pytest
from test_faults_module import BC, Recorder

from phalanx.core.events import Event
from phalanx.core.rng import KeyPath, RngService, StreamRegistry
from phalanx.core.scheduler import System
from phalanx.faults import FaultConfig, FaultInjector, load_catalogue, load_fault_params, load_graph

pytestmark = pytest.mark.unit
SEC = 10**9
#: target -> the kinds a fault may send it (state perturbations of its owner, or hidden truth)
ALLOWED = {
    "health": {"health.fault"},
    "sensors": {"sensor_fault"},
    "monitoring": {"monitor.lru_condition"},
    "utilities": {"util.fault"},
    "fcs": {"fcs.channel_fault", "fcs.actuator_fault", "fcs.wow_fault"},
    "engine": {"eng.fault_inject"},
    "fadec": {"fadec.fault_inject"},
    "airframe": {"af.fault_inject"},
    "maintenance": {"truth.fault", "truth.fault_clear", "truth.incident"},
    "ops": {"ops.start_failure"},
}


@pytest.mark.parametrize("realise_physics_edges", [False, True], ids=["telemetry", "usage"])
def test_every_mode_reaches_only_state_owners(realise_physics_edges):
    cat = load_catalogue()
    sent: dict[str, set[str]] = {}
    for mid, mode in cat.items():
        recs = {k: Recorder(k) for k in ALLOWED if k != "health"}
        recs["health"] = Recorder("health")
        cfg = FaultConfig(
            cat,
            load_graph(),
            {k: k for k in ALLOWED},
            ("IN20-0001",),
            BC,
            realise_physics_edges=realise_physics_edges,
            stochastic=False,
            strict=True,
        )
        f = FaultInjector("faults", load_fault_params(), config=cfg)
        sysm = System(
            [f, *recs.values()],
            [],
            rng=RngService(7, StreamRegistry()),
            identity=KeyPath.of(scenario="A1", tail="KH2011"),
        )
        if not mode.injectable:
            assert mode.process in ("m10", "physics"), mid
            continue
        pay = {"mode": mid, "covered": True}
        if mode.process == "triggered":  # the trigger key M10 would send (a gear leg or a hydraulic system)
            trig = str(
                mode.onset["trigger"]
            )  # gear-leg triggers end in a side (_l/_r/_n), hydraulic ones in 1/2
            trig = trig[:-1] + "l" if trig.endswith(("_?", "_*")) else trig
            pay["key"] = trig.replace("?", "1").replace("*", "1")
        if mid == "FM.SNS.GENERIC":
            pay |= {"sensor_mode": "bias", "key": "ENG.N2.B", "magnitude": 0.01}
        w = sysm.inject(sysm.start(), [Event(SEC, "faults.inject", "faults", pay)])
        w, _ = sysm.run(w, 121 * 240)
        for tgt, r in recs.items():
            kinds = {e.kind for _, e in r.log}
            assert kinds <= ALLOWED[tgt], (mid, tgt, kinds - ALLOWED[tgt])
            sent.setdefault(tgt, set()).update(kinds)
    # the check is not vacuous: every state-owner channel is exercised by the catalogue
    for tgt in ("health", "sensors", "monitoring", "utilities", "fcs", "engine", "fadec", "airframe"):
        assert sent.get(tgt), tgt
