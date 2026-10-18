"""Acceptance A4: the typed dependency graph is acyclic per step; edge transfer functions behave as declared;
propagation reproduces the six AIB cascade templates (engine -> electrical; engine -> AB -> electrical;
hydraulic; utility -> braking; contamination -> control law; electrical -> avionics) in order and inside the
evidenced time windows, for the extreme and median latency draws and for 200 random draws per template."""

from __future__ import annotations

import math

import numpy as np
import pytest

from phalanx.faults.graph import EDGE_TYPES, GraphError, load_graph, parse_graph

G = load_graph()


def _doc(edges, nodes=("a", "b", "c")):
    return {
        "format": "phalanx.fault_graph/1",
        "nodes": {n: {"subsystem": "x"} for n in nodes},
        "edges": [
            {
                "id": f"E{i}",
                "src": s,
                "dst": d,
                "type": "shaft",
                "transfer": {"kind": "gain", "gain": 1.0},
                "latency": lat,
                "mechanism": "graph",
                "evidence": {"tag": "ASSUMPTION", "source": "test"},
            }
            for i, (s, d, lat) in enumerate(edges)
        ],
    }


@pytest.mark.unit
def test_graph_is_acyclic_per_step_and_uses_typed_edges():
    assert G.step_cycle() is None
    order = G.step_order()
    assert set(order) == set(G.nodes)
    pos = {n: i for i, n in enumerate(order)}
    for e in G.instantaneous_edges():
        assert pos[e.src] < pos[e.dst], e.id
    assert {e.type for e in G.edges} <= set(EDGE_TYPES)
    assert {e.type for e in G.edges} == set(EDGE_TYPES)  # every edge type is used
    assert len(G.templates) == 6


@pytest.mark.unit
def test_zero_latency_cycle_is_rejected_but_a_delayed_loop_is_allowed():
    """Negative control: a cycle through instantaneous edges is caught; a loop with a positive latency is a
    cross-step feedback and is allowed."""
    fixed0 = {"dist": "fixed", "s": 0.0}
    g = parse_graph(_doc([("a", "b", fixed0), ("b", "c", fixed0), ("c", "a", fixed0)]))
    assert g.step_cycle() is not None
    with pytest.raises(GraphError):
        g.step_order()
    ok = parse_graph(_doc([("a", "b", fixed0), ("b", "c", fixed0), ("c", "a", {"dist": "fixed", "s": 0.1})]))
    assert ok.step_cycle() is None


@pytest.mark.unit
def test_bad_graph_documents_are_rejected():
    bad = _doc([("a", "b", {"dist": "fixed", "s": 0.0})])
    bad["edges"][0]["type"] = "telepathy"
    with pytest.raises(GraphError):
        parse_graph(bad)
    bad = _doc([("a", "zz", {"dist": "fixed", "s": 0.0})])
    with pytest.raises(GraphError):
        parse_graph(bad)
    bad = _doc([("a", "b", {"dist": "uniform", "lo": 2.0, "hi": 1.0})])
    with pytest.raises(GraphError):
        parse_graph(bad)


@pytest.mark.unit
def test_edge_transfer_functions():
    """gain: y = g x; threshold: 0/1 about θ; lag: first-order rise with τ and time-to-threshold
    -τ ln(1 - θ/y); delay: identity; latency draws: fixed / uniform / log-uniform map u in [0, 1)."""
    lag = next(e for e in G.edges if e.transfer["kind"] == "lag")
    tau = float(lag.transfer["tau_s"])
    y = lag.steady(1.0)
    assert lag.response(1.0, -1.0) == 0.0
    assert lag.response(1.0, tau) == pytest.approx(y * (1 - math.exp(-1)))
    assert lag.response(1.0, 50 * tau) == pytest.approx(y)
    tc = lag.time_to_cross(y, 0.5)
    assert lag.response(1.0, tc) == pytest.approx(0.5)
    assert math.isinf(lag.time_to_cross(0.4, 0.5))
    thr = next(e for e in G.edges if e.transfer["kind"] == "threshold")
    th = float(thr.transfer["threshold"])
    assert thr.steady(th) == 1.0 and thr.steady(th - 1e-9) == 0.0
    gain = next(e for e in G.edges if e.transfer["kind"] == "gain")
    assert gain.steady(0.3) == pytest.approx(0.3 * float(gain.transfer["gain"]))
    delay = next(e for e in G.edges if e.transfer["kind"] == "delay")
    assert delay.steady(0.7) == 0.7 and delay.time_to_cross(0.7, 0.5) == 0.0
    uni = next(e for e in G.edges if e.latency["dist"] == "uniform")
    lo, hi = float(uni.latency["lo"]), float(uni.latency["hi"])
    assert uni.draw_latency(0.0) == lo and uni.draw_latency(0.999999) == pytest.approx(hi, rel=1e-5)
    lg = next(e for e in G.edges if e.latency["dist"] == "loguniform")
    mid = lg.draw_latency(0.5)
    assert mid == pytest.approx(math.sqrt(float(lg.latency["lo"]) * float(lg.latency["hi"])))


@pytest.mark.unit
@pytest.mark.parametrize("tid", sorted(G.templates))
@pytest.mark.parametrize("u", [0.0, 0.5, 0.999999])
def test_templates_reproduce_aib_cascades(tid, u):
    tpl = G.templates[tid]
    acts = G.propagate(tpl.root, uniforms={e.id: u for e in G.edges}, conditions=tpl.conditions)
    assert G.check_template(tid, acts) == []


@pytest.mark.unit
@pytest.mark.parametrize("tid", sorted(G.templates))
def test_templates_hold_for_random_latency_draws(tid):
    """n = 200 random latency draws per template (keyed generator); every draw keeps the order and windows."""
    tpl = G.templates[tid]
    g = np.random.Generator(
        np.random.Philox(np.random.SeedSequence(27, spawn_key=(sorted(G.templates).index(tid),)))
    )
    for _ in range(200):
        acts = G.propagate(tpl.root, uniforms=list(g.random(32)), conditions=tpl.conditions)
        assert G.check_template(tid, acts) == []


@pytest.mark.unit
def test_and_gate_needs_its_condition():
    """Contamination -> control law needs the cold soak: without it the strut never fails (AND gate)."""
    acts = G.propagate("hyd.fluid_contaminated")
    assert "lg.strut_extension_failure" not in {a.node for a in acts}
    acts = G.propagate("hyd.fluid_contaminated", conditions=("env.cold_soak",))
    assert "fcs.ground_law_in_flight" in {a.node for a in acts}


@pytest.mark.unit
def test_mechanism_filter_and_template_check_negative():
    """Telemetry mode realises only 'graph' edges: the physics part of a cascade is left to the modules. The
    template check reports a broken order (negative control)."""
    acts = G.propagate("eng.blade_loss", mechanisms=("graph",))
    assert [a.node for a in acts] == ["eng.blade_loss"]
    good = G.propagate("eng.blade_loss")
    swapped = [a if a.node != "eng.stall" else type(a)(50.0, a.node, a.magnitude, a.via) for a in good]
    problems = G.check_template("T.ENG_AB_ELEC", swapped)
    assert any("order" in p for p in problems) and any("outside" in p for p in problems)
