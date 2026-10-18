"""M10 at the AD-44 boundary: ``usage.sortie_summary`` expansion (design-usage rates; the Nz PROXY exposed),
``cfg.install`` / ``cfg.remove`` / ``mx.repaired`` (unit states travel with their serial), ``mx.action``
(wash, servicing, latent-defect forwarding), per-tail filtering of fleet-level events, the position map
against the M18 catalogue, and the BeliefTarget protocol.

TEST FIXTURES: ``Recorder`` modules stand in for M11 and M14 at the module boundary. Events are built in the
AD-48.1 plain-key encoding (``plain_payload``). Sample: one tail, ≤ 6 sorties per test (deterministic
mechanisms)."""

from __future__ import annotations

import json

import numpy as np
import pytest

from phalanx.core.canonical import canonical_json
from phalanx.core.events import Event
from phalanx.core.module import ModuleBase, ParamSet
from phalanx.core.rng import KeyPath, RngService, StreamRegistry
from phalanx.core.scheduler import System
from phalanx.dictionary import load_dictionary
from phalanx.health import HealthConfig, HealthModule, load_health_params, sensor_bias_channels
from phalanx.health.layout import AIRFRAME_NAMES
from phalanx.health.module import _EF, _EI, _EL, POSITIONS
from phalanx.health.protocol import POSITION_STATES, plain_payload, read_payload
from phalanx.health.usage import NZ_LEVELS_DEFAULT, nz_counter_kernel, summary_payload, usage_from_summary
from phalanx.maintenance.config import load_m18_config
from phalanx.monitoring import load_code_table, load_monitoring_params

pytestmark = pytest.mark.unit
D = load_dictionary()
P = load_health_params()
SEC = 10**9
H = 3600 * SEC


class Recorder(ModuleBase):  # TEST FIXTURE (module boundary): records the events addressed to it
    version = "0.0.1"
    rate = None

    def __init__(self, id):
        super().__init__(id, ParamSet("rec", {}))
        self.log: list[tuple[int, Event]] = []

    def init(self, params, keys):
        return {}

    def on_event(self, state, event, t):
        self.log.append((int(t), event))
        return state, []


def doc_event(t, kind, doc, target="m10"):
    """An operations event in the AD-48.1 plain-key encoding."""
    return Event(int(t), kind, target, plain_payload(doc), source="test")


def summary(k, *, hours=1.0, tail="T01", **kw):
    d = {
        "sortie_id": f"{tail}-{k}",
        "tail_no": tail,
        "flight_hours": hours,
        "engine_cycles": 2.5 * hours,
        "engine_starts": 1,
        "landings": 1,
        "time_at_temp_s": 600.0,
        "max_nz": 5.5,
        "ab_time_s": 180.0,
        "dust_index": 1.0,
        "salt_index": 1.0,
    }
    d.update(kw)
    return d


def build(*, targets=True):
    recs = [Recorder("m11"), Recorder("m14")] if targets else []
    cfg = HealthConfig(
        ("IN20-0001",),
        sensor_bias_channels(D),
        "m11" if targets else None,
        monitor_target="m14" if targets else None,
    )
    m10 = HealthModule("m10", P, config=cfg, identity={"tail": "T01"})
    sysm = System(
        [m10, *recs], [], rng=RngService(0x10, StreamRegistry()), identity=KeyPath.of(scenario="S1")
    )
    return sysm, m10, {r.id: r for r in recs}


def run(sysm, w, events, until_ns):
    w = sysm.inject(w, events)
    return sysm.run(w, until_ns // (SEC // 240) + 2 - w.k)[0]


# ---------------------------------------------------------------------------------------------- summary
def test_summary_expansion_matches_design_rates():
    u = usage_from_summary(summary(0), P, 1)
    ft = 3600.0
    assert u.flight_time_s == ft and u.eot_s[0] == pytest.approx(1.35 * ft)
    assert u.type1[0] == 1.0 and u.starts[0] == 1.0 and u.tamp_s[0] == 600.0
    assert u.tac()[0] == pytest.approx(2.5)  # engine_cycles read as the sortie TAC
    assert u.type4[0] / u.type3[0] == pytest.approx(5.52 / 5.13, rel=1e-3)  # design ratio
    assert u.ab_lights[0] == pytest.approx(180.0 * 108.8 / 3600.0)
    assert u.eftc[0] == pytest.approx(1.0 + 0.2 * u.type3[0] + 0.03 * u.type4[0])
    assert u.src_h[0] == pytest.approx(600.0 / 3600.0 + 0.05 * (1.35 * ft - 600.0) / 3600.0)
    no_tac = usage_from_summary(summary(0, engine_cycles=0.0), P, 1)
    assert no_tac.type3[0] == pytest.approx(5.13) and no_tac.type4[0] == pytest.approx(5.52)
    # telemetry mode: the full usage travels in the doc and comes back exactly (through JSON)
    doc = json.loads(canonical_json(summary_payload(u, "T01", max_nz=5.5)).decode())
    assert usage_from_summary(doc, P, 1) == u


def test_nz_from_max_nz_is_a_lower_bound():
    """PROXY A-W1.5-18 exposed: three pulls to 5.5 g count three crossings per level in the truth counter;
    the summary expansion gives one, never more than the truth."""
    u = usage_from_summary(summary(0), P, 1)
    t = np.linspace(0.0, 60.0, 6001)
    nz = 1.0 + 4.5 * np.sin(2 * np.pi * t / 20.0)  # three pulls to 5.5 g with pushes through 1 g (re-arm)
    truth, _ = nz_counter_kernel(
        np.zeros(8), np.ones(8, np.int64), np.asarray(NZ_LEVELS_DEFAULT), 1.0, nz.astype(np.float64)
    )
    assert u.nz_counts == (0.0, 0.0, 1.0, 1.0, 1.0, 1.0, 0.0, 0.0)
    assert np.all(np.asarray(u.nz_counts) <= truth) and truth[2] == 3.0


def test_summary_forwards_a_usage_mode_sortie_only():
    sysm, _m10, recs = build()
    w = run(sysm, sysm.start(), [doc_event(2 * H, "usage.sortie_summary", summary(0))], 2 * H + SEC)
    kinds = [e.kind for _, e in recs["m11"].log]
    assert kinds == ["faults.sortie_start", "faults.sortie_end"]
    start = recs["m11"].log[0][1].payload
    assert float(start["window_s"]) == 0.0 and float(start["duration_s"]) == 3600.0
    ((t14, e14),) = recs["m14"].log
    assert e14.kind == "monitor.usage_sortie" and int(e14.payload["t_start"]) == H and t14 == 2 * H
    assert int(w.states["m10"]["clock"][0]) == 1  # one sortie of usage
    # telemetry mode (full usage in the doc): M11 and M14 follow the sortie themselves
    u = usage_from_summary(summary(1), P, 1)
    w = run(sysm, w, [doc_event(4 * H, "usage.sortie_summary", summary_payload(u, "T01"))], 4 * H + SEC)
    assert len(recs["m11"].log) == 2 and len(recs["m14"].log) == 1
    # another tail's summary is ignored (fleet-level events, one M10 per tail)
    w = run(sysm, w, [doc_event(5 * H, "usage.sortie_summary", summary(2, tail="T02"))], 5 * H + SEC)
    assert int(w.states["m10"]["clock"][0]) == 2


# ---------------------------------------------------------------------------------------------- units
def test_every_m18_position_is_mapped():
    """The SYNTHETIC position map covers the W1.8 catalogue exactly and names only existing states/LRUs."""
    cat = load_m18_config().catalogue
    assert set(POSITION_STATES) == {p.code for p in cat.positions}
    assert POSITIONS == tuple(POSITION_STATES)
    lrus = {c.lru for c in load_code_table(D, load_monitoring_params()).codes}
    for pos, items in POSITION_STATES.items():
        for item in items:
            kind, _, rest = item.partition(":")
            if kind == "air":
                assert rest in AIRFRAME_NAMES, (pos, item)
            elif kind == "eng":
                assert rest.split(":")[1] in _EF, (pos, item)
            elif kind == "lru":
                assert rest in lrus, (pos, item)
            else:
                assert kind == "engine", (pos, item)


def test_unit_states_travel_with_their_serial():
    sysm, _m10, recs = build()
    ev = [doc_event(0, "cfg.install", {"tail": "T01", "pos": "ENG", "serial": "SYN-E1", "cls": "ENG"})]
    ev += [doc_event(0, "cfg.install", {"tail": "T01", "pos": "HYDP1", "serial": "SYN-P1", "cls": "HYDP"})]
    ev += [doc_event((k + 1) * 6 * H, "usage.sortie_summary", summary(k)) for k in range(4)]
    w = run(sysm, sysm.start(), ev, 25 * H)
    st = w.states["m10"]
    assert str(st["eng_serial"][0]) == "SYN-E1" and int(st["eng_i"][0][_EI["flights"]]) == 4
    e1 = {k: np.array(st[k][0], copy=True) for k in ("eng_f", "eng_i", "eng_life")}
    p1 = float(st["air"][AIRFRAME_NAMES.index("hyd1_pump_wear")])
    swap = [
        doc_event(26 * H, "cfg.remove", {"tail": "T01", "pos": "ENG", "serial": "SYN-E1"}),
        doc_event(26 * H, "cfg.install", {"tail": "T01", "pos": "ENG", "serial": "SYN-E2", "cls": "ENG"}),
    ]
    w = run(sysm, w, swap, 27 * H)
    st = w.states["m10"]
    assert str(st["eng_serial"][0]) == "SYN-E2" and int(st["eng_i"][0][_EI["flights"]]) == 0
    assert not np.array_equal(st["eng_f"][0], e1["eng_f"])
    back = [
        doc_event(28 * H, "cfg.remove", {"tail": "T01", "pos": "ENG", "serial": "SYN-E2"}),
        doc_event(28 * H, "cfg.install", {"tail": "T01", "pos": "ENG", "serial": "SYN-E1", "cls": "ENG"}),
    ]
    w = run(sysm, w, back, 29 * H)
    st = w.states["m10"]
    for k, v in e1.items():
        assert np.array_equal(st[k][0], v), k  # the used engine came back with its states, bitwise
    assert float(st["air"][AIRFRAME_NAMES.index("hyd1_pump_wear")]) == p1
    # a repaired unit is renewed: its next install builds a fresh unit (new draws), not the old states
    rep = [
        doc_event(30 * H, "cfg.remove", {"tail": "T01", "pos": "ENG", "serial": "SYN-E1"}),
        doc_event(30 * H, "mx.repaired", {"serial": "SYN-E1", "level": "depot"}),
        doc_event(31 * H, "cfg.install", {"tail": "T01", "pos": "ENG", "serial": "SYN-E1", "cls": "ENG"}),
    ]
    w = run(sysm, w, rep, 32 * H)
    st = w.states["m10"]
    assert int(st["eng_i"][0][_EI["flights"]]) == 0 and st["eng_life"][0][_EL["eot_s"]] == 0.0
    assert st["eng_f"][0][_EF["init_fan_eta"]] != e1["eng_f"][_EF["init_fan_eta"]]
    # M11 and M14 heard about the installs (W1.5-internal forwarding)
    kinds = [e.kind for _, e in recs["m11"].log]
    assert kinds.count("faults.install") == 5
    assert [read_payload(e.payload)["pos"] for _, e in recs["m11"].log if e.kind == "faults.install"][:2] == [
        "ENG",
        "HYDP1",
    ]


def test_mx_actions_wash_service_and_latent_forwarding():
    sysm, _m10, recs = build()
    ev = [doc_event((k + 1) * 6 * H, "usage.sortie_summary", summary(k, dust_index=3.0)) for k in range(3)]
    w = run(sysm, sysm.start(), ev, 19 * H)
    f0 = float(w.states["m10"]["eng_f"][0][_EF["foul_hpc"]])
    tyre = AIRFRAME_NAMES.index("tyre_p_loss_l")
    assert f0 > 0.0 and float(w.states["m10"]["air"][tyre]) > 0.0
    acts = [
        doc_event(
            20 * H, "mx.action", {"tail": "T01", "pos": "ENG", "action": "ENGINE_WASH", "job_no": "J1"}
        ),
        doc_event(20 * H, "mx.action", {"tail": "T01", "pos": None, "action": "TYRES", "job_no": "J2"}),
        doc_event(
            20 * H, "mx.action", {"tail": "T01", "action": "SWLOAD", "sw_config_id": "SW2", "job_no": "J3"}
        ),
        doc_event(
            20 * H, "mx.action", {"tail": "T02", "pos": "ENG", "action": "ENGINE_WASH", "job_no": "J4"}
        ),
    ]
    w = run(sysm, w, acts, 21 * H)
    st = w.states["m10"]
    assert float(st["eng_f"][0][_EF["foul_hpc"]]) == pytest.approx(f0 * (1.0 - float(P.value("wash_rho"))))
    assert float(st["air"][tyre]) == 0.0
    fwd = [read_payload(e.payload) for _, e in recs["m11"].log if e.kind == "faults.maintenance"]
    assert fwd == [{"job": "J3", "action": "software_load"}]


# ---------------------------------------------------------------------------------------------- belief
def test_belief_target_protocol():
    from phalanx.fork.belief import BeliefTarget

    sysm, m10, _ = build(targets=False)
    w = run(
        sysm,
        sysm.start(),
        [doc_event(0, "cfg.install", {"tail": "T01", "pos": "ENG", "serial": "SYN-E1", "cls": "ENG"})],
        SEC,
    )
    st = w.states["m10"]
    for name in ("belief_items", "belief_prior", "with_belief"):
        assert callable(getattr(m10, name)) and hasattr(BeliefTarget, name)
    assert m10.belief_items(st) == ["SYN-E1"]
    fam, prm = m10.belief_prior(st, "SYN-E1")
    assert fam == "weibull" and prm["shape"] == pytest.approx(1.5) and prm["scale_h"] == pytest.approx(8000.0)
    st2 = m10.with_belief(st, {"SYN-E1": {"u_s": 3600.0 * 100, "th_s": 3600.0 * 900}}, set())
    assert (
        st2["eng_life"][0][_EL["eot_s"]] == 3600.0 * 100
        and st2["eng_f"][0][_EF["spall_life"]] == 3600.0 * 900
    )
    assert int(st2["eng_i"][0][_EI["spall_on"]]) == 0
    assert np.array_equal(st["eng_f"][0], w.states["m10"]["eng_f"][0])  # the input state is not modified
