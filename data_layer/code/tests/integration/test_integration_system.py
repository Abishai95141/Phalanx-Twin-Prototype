"""W2.1 deliverable 1: the telemetry System is built from the published ``ports.py`` bindings (never
hand-wired).

Checks on the System of the first flying sortie of the realised-usage gate sample (plan order, scenario
'gate', root 0xA5; ``phalanx.integration.plans.gate_sorties``), n = 1 plan:

- every input of every module is connected to the producer its binding names (catalogue key or M13 lane), and
  to nothing else; tracked conformance exceptions would get a labelled PROXY boundary source and nothing more
  (none since the W2.2 ENG.AB_LIT producer: the FADEC reads the M13 lane of the M12 UV flame detector);
- every one-frame delay is a documented back-edge, every documented back-edge is used, and an undocumented one
  or a missing producer fails the build (negative controls);
- per-tail configuration is in the config hash (AD-48.8): another engine serial changes it;
- the DFCC computes on its lanes (PD-W2.1a-1) and, in the architecture-§8 order behind a delayed lane edge, it
  reads empty buffers (the measured M05 defect behind the proposed decision);
- M11 effect targets left unwired because the consumer has no handler yet are still unhandled (stale check).
"""

from __future__ import annotations

from dataclasses import replace

import numpy as np
import pytest

from phalanx.core.module import ContractError, EventNotHandledError
from phalanx.integration.plans import gate_sorties
from phalanx.integration.system import (
    CONTINUOUS_ORDER,
    M_ID,
    OBSERVATION_ORDER,
    PREFIX_OF,
    UNHANDLED_FAULT_TARGETS,
    BoundaryHold,
    SortieSpec,
    _package_bindings,
    build_sortie_system,
)
from phalanx.integration.wiring import BACK_EDGES, connections, tracked_exceptions

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def plan():
    return gate_sorties()[0]


@pytest.fixture(scope="module")
def ss(plan):
    return build_sortie_system(SortieSpec(plan=plan, scenario="gate", root=0xA5, fused=False))


def _producers(ss) -> dict[str, str]:
    out = {}
    for mid, m in ss.modules.items():
        pre = PREFIX_OF.get(mid)
        if pre is None:
            continue
        for p in m.ports_out:
            out[f"{pre}.{p.name}"] = f"{mid}.{p.name}"
    for lid in ("acq_fadec", "acq_dfcc"):
        for lane, port in ss.modules[lid].lane_bindings().items():
            out[lane] = f"{lid}.{port}"
    return out


def test_every_input_is_wired_from_its_published_binding(ss):
    bindings = _package_bindings(len(ss.window.engine_serials))
    prods = _producers(ss)
    dst = {c.dst: c for c in ss.connections}
    n_inputs = 0
    tracked = {sig for _port, sig, _exc in ss.exceptions_used}
    for mid in (*CONTINUOUS_ORDER, *OBSERVATION_ORDER):
        for p in ss.modules[mid].ports_in:
            n_inputs += 1
            sig = bindings[mid][p.name]
            c = dst[f"{mid}.{p.name}"]
            if sig in tracked:
                src_mod = c.src.split(".")[0]
                assert isinstance(ss.modules[src_mod], BoundaryHold), c
                assert all(prm.proxy for prm in ss.modules[src_mod].params.values())
            else:
                assert c.src == prods[sig], (mid, p.name, sig, c.src)
    assert n_inputs == len(ss.connections)  # nothing wired beyond the bindings
    # no boundary left: the AB flame-detector lane is M13's (W2.2, c325285; conformance exceptions empty)
    assert tracked == set()
    assert dst["fadec.ab_lit"].src == prods["lane.ENG.AB_LIT"]
    assert prods["lane.ENG.AB_LIT"].startswith("acq_fadec.")


def test_back_edges_are_the_documented_one_frame_delays(ss):
    order = {mid: k for k, mid in enumerate(ss.system.order)}
    used = set()
    for c in ss.connections:
        sm, dm = c.src.split(".")[0], c.dst.split(".")[0]
        back = order[sm] >= order[dm]
        assert c.delayed == back, c
        if back:
            key = (PREFIX_OF[sm], PREFIX_OF[dm])
            assert c.note == BACK_EDGES[key]
            used.add(key)
    assert used == set(BACK_EDGES), f"documented but unused back-edges: {set(BACK_EDGES) - used}"


def test_undocumented_back_edge_and_missing_producer_fail_the_build(ss):
    """Negative controls: the engine moved behind the airframe makes eng.thrust -> af an undocumented
    back-edge; without M13's AB_LIT lane the FADEC input has no producer; a tracked exception (a synthetic
    one: the catalogue has none left) needs its labelled boundary source, and a boundary source needs a
    tracked exception."""
    mods = [ss.modules[m] for m in ss.system.order]
    bindings = _package_bindings(1)
    bindings = {mid: {p.name: b[p.name] for p in ss.modules[mid].ports_in} for mid, b in bindings.items()}
    lanes = {lid: ss.modules[lid].lane_bindings() for lid in ("acq_fadec", "acq_dfcc")}
    exc = tracked_exceptions("e1")
    assert exc == ()
    from phalanx.integration.wiring import Source, TrackedException

    conns, _ = connections(mods, bindings, PREFIX_OF, lanes, m_id=M_ID, exceptions=exc, boundary={})
    assert len(conns) == len(ss.connections)
    swapped = list(mods)
    i_eng, i_af = swapped.index(ss.modules["eng"]), swapped.index(ss.modules["af"])
    swapped[i_eng], swapped[i_af] = swapped[i_af], swapped[i_eng]
    with pytest.raises(ContractError, match="not a documented one-frame delay"):
        connections(swapped, bindings, PREFIX_OF, lanes, m_id=M_ID, exceptions=exc, boundary={})
    no_lane = {**lanes, "acq_fadec": {k: v for k, v in lanes["acq_fadec"].items() if k != "lane.ENG.AB_LIT"}}
    with pytest.raises(ContractError, match="no producer"):
        connections(mods, bindings, PREFIX_OF, no_lane, m_id=M_ID, exceptions=exc, boundary={})
    synth = (TrackedException("lane_producer", "lane.ENG.AB_LIT", ("M08",), "test", "negative control"),)
    with pytest.raises(ContractError, match="labelled boundary source"):
        connections(mods, bindings, PREFIX_OF, no_lane, m_id=M_ID, exceptions=synth, boundary={})
    boundary = {"lane.ENG.AB_LIT": Source("hold_ab_lit", "lane_eng_ab_lit")}
    with pytest.raises(ContractError, match="not a tracked exception"):
        connections(mods, bindings, PREFIX_OF, no_lane, m_id=M_ID, exceptions=(), boundary=boundary)


def test_config_hash_covers_serials_and_tail_configuration(plan, ss):
    """AD-48.8: the per-tail configuration is hashed; another engine serial gives another config hash."""
    again = build_sortie_system(SortieSpec(plan=plan, scenario="gate", root=0xA5, fused=False))
    assert again.system.config_hash == ss.system.config_hash
    other = build_sortie_system(
        SortieSpec(
            plan=replace(plan, engine_serials=("IN20-OTHER",)), scenario="gate", root=0xA5, fused=False
        )
    )
    assert other.system.config_hash != ss.system.config_hash
    cfg = ss.modules["sortie_config"].params
    assert list(np.asarray(cfg.value("engine_serials"))) == list(plan.engine_serials)


def test_dfcc_computes_on_its_lanes_and_not_behind_a_delayed_lane_edge(plan, ss):
    """PD-W2.1a-1. With the DFCC after its lanes, its voted Nz on the gear is the measured specific force
    (|g| within 3 %, n = 0.5 s of frames after a 0.5 s settle). In the architecture-§8 order (FCS before the
    lanes, so the lane edge is a delayed back-edge) M05 frames on samples the delayed buffer does not hold:
    its voted Nz stays exactly 0 (the M05 timing defect reported to W2.1c)."""
    w = ss.system.inject(ss.start(), ss.bootstrap_events())
    _, tr = ss.system.run(w, 240, record=["fcs.rec_fcs_voted_nz"])
    vnz = tr.ports["fcs.rec_fcs_voted_nz"][120:]
    assert np.all(np.abs(vnz - 9.80665) < 0.03 * 9.80665), vnz[:12]
    order = ("env", "pilot", "fcs", "fadec", "eng", "af", "util", "sens", "acq_fadec", "acq_dfcc")
    with pytest.raises(ContractError, match="not a documented one-frame delay"):
        build_sortie_system(
            SortieSpec(plan=plan, scenario="gate", root=0xA5, fused=False, continuous_order=order)
        )


def test_architecture_order_reads_empty_dfcc_lanes(plan, monkeypatch):
    """Negative control for PD-W2.1a-1: with the three FCS back-edges the §8 order needs documented, the
    System builds, and M05 reads only zeros from its lanes (voted Nz 0 on the gear)."""
    from phalanx.integration import wiring

    extra = {
        ("af", "fcs"): "test: airframe -> FCS in the architecture-§8 order",
        ("util", "fcs"): "test: utilities -> FCS in the architecture-§8 order",
        ("acq", "fcs"): "test: DFCC lanes -> FCS as a delayed back-edge (W2.1 brief)",
    }
    monkeypatch.setattr(wiring, "BACK_EDGES", {**wiring.BACK_EDGES, **extra})
    order = ("env", "pilot", "fcs", "fadec", "eng", "af", "util", "sens", "acq_fadec", "acq_dfcc")
    s8 = build_sortie_system(
        SortieSpec(plan=plan, scenario="gate", root=0xA5, fused=False, continuous_order=order)
    )
    w = s8.system.inject(s8.start(), s8.bootstrap_events())
    _, tr = s8.system.run(w, 240, record=["fcs.rec_fcs_voted_nz", "acq_dfcc.lane_fcs_asa_nz_a_n"])
    assert np.all(tr.ports["fcs.rec_fcs_voted_nz"][120:] == 0.0)
    assert tr.ports["acq_dfcc.lane_fcs_asa_nz_a_n"].sum() == 80  # the lane did deliver 80 Hz samples


def test_unwired_fault_targets_are_still_unhandled(ss):
    """M11 effects whose catalogued kind has no handler in the target module are left unwired (tracked). When
    a handler lands (W2.1b M07/M08, W2.1c M06), this fails: remove the entry so the effects are wired."""
    from phalanx.core.events import Event
    from phalanx.integration.system import FAULT_TARGETS

    for target, (kind, owner) in UNHANDLED_FAULT_TARGETS.items():
        mod = ss.modules[FAULT_TARGETS[target]]
        st = ss.system.start().states[mod.id]
        payload = {
            "tail": ss.window.tail,
            "mode": "x",
            "param": 0.0,
            "instance": 0,
            "engine": 0,
            "clear": False,
            "leg": -1,
        }
        with pytest.raises(EventNotHandledError):  # a ContractError would come from a handler: handled
            mod.on_event(st, Event(0, kind, mod.id, payload), 0)
        assert owner.startswith("W2.1")


def test_fadec_p0_is_the_initialised_air_data_altitude_signal(ss):
    """W2.2 (f1b3bc9): on the Tejas M08's P0 is the avionics ADC's ``p0_from_hp`` (a documented one-frame
    back-edge, fused with the truth loop). The ADC starts at the field static pressure (post-start initial
    condition, ``initial.adc_at_field``), so M08's first frame reads the field P0, not the cold ADC's
    101,325 Pa at zero altitude; over the first second the signal tracks the truth static pressure to 0.1 %
    (parked: the position error is nil), n = 1 plan, 240 steps."""
    c = {c.dst: c for c in ss.connections}["fadec.p0"]
    assert c.src == "avio.p0_from_hp" and c.delayed
    w = ss.start()
    p_s = float(w.held["env.p_s"])
    assert abs(float(w.held["avio.p0_from_hp"]) - p_s) < 1e-3, (float(w.held["avio.p0_from_hp"]), p_s)
    w = ss.system.inject(w, ss.bootstrap_events())
    _, tr = ss.system.run(w, 240, record=["avio.p0_from_hp", "env.p_s"])
    rel = np.abs(tr.ports["avio.p0_from_hp"] / tr.ports["env.p_s"] - 1.0)
    assert rel.max() < 1e-3, rel.max()
