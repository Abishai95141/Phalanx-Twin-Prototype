"""E1-MF (m10): M11 honours a graph edge's declared latency at module level: no effect before it, one after.

E1 mutant m10 (M11 edge latency -> 0) survived: the graph unit tests check `propagate` and the templates,
and the module tests check cascade *order*, but nothing checked *when* the injector delivers a cascade
node's effect to the module that owns the state. Here the real injector runs a documented cascade
(architecture §9.2, Tejas: brake-software defect -> tyre burst -> runway excursion; graph edges G40 and G41,
mechanism `graph`, so M11 realises them in usage and telemetry mode alike) and the effects reach TEST FIXTURE
recorders at the module boundary (they only log the events they receive).

Expected times come from the edge declarations in `configs/tejas/faults/graph.yaml` (the `latency` mapping:
uniform lo/hi) and the instance's latency variates, re-drawn here from M11's declared `faults.instance`
stream in the documented `_draw_instance` order (severity u and z, coverage u, 16 latency uniforms consumed
in traversal order). Neither `FaultGraph.propagate` nor `Edge.draw_latency` is used, so a mutant in either
cannot move the expectation with it. M11 stamps a node's effects at the frame its `faults.node` event is
dispatched: the first truth frame at or after the exact node time (AD-36, at most 1/240 s later). Checks: each
node's effect arrives exactly there, exactly once and never before the exact time; and, whatever the draw, the
second hop comes at least G41's minimum latency (0.5 s, less one frame) after the first.

Sample: one scripted fault per mode (usage, telemetry), 42 s of simulated time.
"""

from __future__ import annotations

import pytest

from phalanx.core.events import Event
from phalanx.core.module import ModuleBase, ParamSet
from phalanx.core.rng import KeyPath, RngService, StreamRegistry
from phalanx.core.scheduler import System
from phalanx.core.time import latest_truth_step, truth_step_time_ns
from phalanx.dictionary import load_dictionary
from phalanx.faults import FaultConfig, FaultInjector, load_catalogue, load_fault_params, load_graph
from phalanx.health import sensor_bias_channels

pytestmark = pytest.mark.unit
SEC = 10**9
T0 = 2 * SEC
MODE = "FM.LG.BRAKE_SW_CONFIG"
CHAIN = (("G40", "tyre_burst"), ("G41", "runway_excursion"))  # (edge, airframe fault mode of its destination)
N_LAT = 16


class Recorder(ModuleBase):  # TEST FIXTURE (module boundary): records received events
    version = "0.0.1"
    rate = None

    def __init__(self, id):
        super().__init__(id, ParamSet("rec", {}))
        self.log: list[tuple[int, Event]] = []

    def init(self, params, keys):
        return {}

    def on_event(self, state, event, t):
        self.log.append((t, event))
        return state, []


def _run(usage_mode: bool):
    recs = {k: Recorder(k) for k in ("airframe", "monitoring")}
    graph = load_graph()
    f = FaultInjector(
        "faults",
        load_fault_params(),
        config=FaultConfig(
            load_catalogue(),
            graph,
            {k: k for k in recs},
            ("IN20-0001",),
            sensor_bias_channels(load_dictionary()),
            realise_physics_edges=usage_mode,
            stochastic=False,
        ),
    )
    sysm = System(
        [f, *recs.values()],
        [],
        rng=RngService(0xFA17, StreamRegistry()),
        identity=KeyPath.of(scenario="S1", tail="KH2011"),
    )
    w = sysm.inject(sysm.start(), [Event(T0, "faults.inject", "faults", {"mode": MODE})])
    sysm.run(w, 240 * 42)
    g = f.stream("instance", event=0).generator(0)  # instance 0: the scripted fault
    g.random(), g.standard_normal(), g.random()  # severity u, z; coverage u
    lat = g.random(N_LAT)
    deliveries = sorted((e.t_ns, str(e.payload["mode"])) for _, e in recs["airframe"].log)
    return graph, lat, deliveries


def _edge(graph, edge_id: str):
    e = next(x for x in graph.edges if x.id == edge_id)
    assert e.latency["dist"] == "uniform" and e.mechanism == "graph" and e.transfer["kind"] == "gain"
    return e


def _declared_latency_s(graph, edge_id: str, u: float) -> float:
    """Latency from the YAML declaration (uniform lo/hi) and the variate: independent of Edge.draw_latency."""
    lat = _edge(graph, edge_id).latency
    return float(lat["lo"]) + u * (float(lat["hi"]) - float(lat["lo"]))


def first_frame_at_or_after(t_ns: int) -> int:
    k = latest_truth_step(t_ns)
    return t_ns if truth_step_time_ns(k) == t_ns else truth_step_time_ns(k + 1)


FRAME_NS = truth_step_time_ns(1)


def latency_problems(graph, lat, deliveries) -> list[str]:
    out = []
    t_s = 0.0
    prev = None
    for hop, (edge_id, mode) in enumerate(CHAIN):
        t_s += _declared_latency_s(graph, edge_id, float(lat[hop]))  # variates consumed in traversal order
        exact = T0 + round(t_s * 1e9)
        expected = first_frame_at_or_after(exact)
        got = [t for t, m in deliveries if m == mode]
        if got != [expected]:
            out.append(
                f"{mode}: delivered at {got}, declared latency puts it at [{expected}] (exact {exact})"
            )
        if any(t < exact for t in got):
            out.append(f"{mode}: delivered before the declared latency elapsed ({exact})")
        lo_ns = round(float(_edge(graph, edge_id).latency["lo"]) * 1e9) - FRAME_NS
        if prev is not None and got and got[0] - prev < lo_ns:
            out.append(f"{mode}: {got[0] - prev} ns after its source, below the {edge_id} minimum {lo_ns} ns")
        prev = got[0] if got else prev
    return out


@pytest.mark.parametrize("usage_mode", [True, False])
def test_cascade_effects_arrive_at_the_declared_edge_latencies(usage_mode):
    graph, lat, deliveries = _run(usage_mode)
    # not vacuous: the chain must declare a strictly positive latency (pick another edge if the data change)
    assert float(_edge(graph, "G41").latency["lo"]) > 0 and all(0.0 < u < 1.0 for u in lat[:2])
    assert [m for _, m in deliveries] == ["tyre_burst", "runway_excursion"], deliveries
    assert latency_problems(graph, lat, deliveries) == []


def test_latency_check_rejects_a_zero_latency_delivery():
    """Negative control: the recorded deliveries with the second hop moved onto the first (the m10 shape) and
    with both hops at the onset are each rejected."""
    graph, lat, deliveries = _run(True)
    (t1, m1), (_t2, m2) = deliveries
    assert latency_problems(graph, lat, [(t1, m1), (t1, m2)])
    assert any("below the G41 minimum" in p for p in latency_problems(graph, lat, [(t1, m1), (t1, m2)]))
    assert latency_problems(graph, lat, [(T0, m1), (T0, m2)])
