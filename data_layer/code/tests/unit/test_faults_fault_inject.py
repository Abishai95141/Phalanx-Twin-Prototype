"""AD-48.4 (W2.1c): M11 constructs all three catalogued physical fault-injection kinds from its fault
templates - ``eng.fault_inject`` (-> M07), ``fadec.fault_inject`` (-> M08) and ``af.fault_inject`` (-> M06,
with the gear leg) - with the catalogued plain-key payload; a clear repeats the onset's addressing (the
instance's choice variate is kept, so a ``"*"`` channel or leg clears the one it set).

TEST FIXTURES: ``Recorder`` modules stand in for M07 / M08 / M06 / M05 at the module boundary
(``test_faults_module.build``). The M06 end of ``af.fault_inject`` is tested against the real M06 in
``tests/integration/test_airframe_fault_inject.py``; the M07 / M08 handlers are W2.1b's. Sample: one tail,
scripted or triggered faults (n = 1 instance per kind; 8 instances for the clear-addressing check).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from test_faults_module import SEC, build, run_to

from phalanx.core.events import Event
from phalanx.core.module import ContractError
from phalanx.dictionary.yamlio import load_yaml
from phalanx.faults import load_catalogue
from phalanx.faults.catalogue import airframe_effect_errors
from phalanx.health.protocol import read_payload

pytestmark = pytest.mark.unit
CAT = load_yaml(Path(__file__).resolve().parents[2] / "configs" / "interfaces" / "w1_events.yaml")["events"]


def _received(recs, target, kind):
    return [(t, read_payload(e.payload)) for t, e in recs[target].log if e.kind == kind]


def _check_payload(kind, d):
    assert set(CAT[kind]["payload"]) <= set(d), (kind, sorted(d))
    assert CAT[kind]["producer"] == "M11" and CAT[kind]["hidden"] is True


@pytest.mark.parametrize(
    "mode, target, kind",
    [
        ("FM.ENG.SHUTOFF_PARTIAL", "engine", "eng.fault_inject"),
        ("FM.ENG.FUEL_SCHEDULE_BIAS", "fadec", "fadec.fault_inject"),
    ],
)
def test_engine_and_fadec_kinds_are_constructed_from_templates(mode, target, kind):
    sysm, _f, _h, recs = build()
    w = sysm.inject(sysm.start(), [Event(SEC, "faults.inject", "faults", {"mode": mode, "covered": True})])
    w = run_to(sysm, w, 2 * SEC)
    got = _received(recs, target, kind)
    assert len(got) == 1
    d = got[0][1]
    _check_payload(kind, d)
    eff = next(e for e in load_catalogue()[mode].effects if e.target == target)
    assert d["mode"] == eff.fields["mode"] and d["tail"] == "KH2011" and d["clear"] is False
    assert "leg" not in d  # the gear leg is an airframe field only


def test_airframe_kind_carries_the_triggering_legs():
    """FM.LG.DOWNLOCK_FORCE is triggered by M10's lock-spring state of one leg (``util:lock_spring_r``): its
    af.fault_inject names that leg (2, right main)."""
    sysm, _f, _h, recs = build()
    trig = Event(SEC, "faults.trigger", "faults", {"trigger": "util:lock_spring_r"})
    run_to(sysm, sysm.inject(sysm.start(), [trig]), 2 * SEC)
    got = _received(recs, "airframe", "af.fault_inject")
    assert [d["mode"] for _, d in got] == ["gear_collapse_on_touchdown"]
    _check_payload("af.fault_inject", got[0][1])
    assert got[0][1]["leg"] == 2


def test_graph_nodes_emit_airframe_legs():
    """A cascade node with ``legs: [1, 2]`` (strut extension failure, cold-soaked water contamination) emits
    one af.fault_inject per main leg."""
    sysm, _f, _h, recs = build()
    ev = Event(
        SEC,
        "faults.inject",
        "faults",
        {"mode": "FM.HYD.WATER_CONTAMINATION", "covered": True, "cold_soak": 1.0},
    )
    run_to(sysm, sysm.inject(sysm.start(), [ev]), 4000 * SEC)
    legs = sorted(d["leg"] for _, d in _received(recs, "airframe", "af.fault_inject"))
    assert legs == [1, 2]


def test_clear_addresses_the_channel_the_onset_set():
    """An FCS channel dropout picks its channel with the instance's choice variate ("*"); its clear 5 s later
    names the same channel (W1 cleared with a fixed 0.5 choice, i.e. channel 2 whatever was set)."""
    sysm, _f, _h, recs = build()
    evs = [
        Event(
            (10 + 20 * k) * SEC,
            "faults.inject",
            "faults",
            {"mode": "FM.FCS.CHANNEL_DROPOUT", "covered": True},
        )
        for k in range(8)
    ]
    run_to(sysm, sysm.inject(sysm.start(), evs), 200 * SEC)
    got = _received(recs, "fcs", "fcs.channel_fault")
    on = [d["channel"] for _, d in got if d["active"]]
    off = [d["channel"] for _, d in got if not d["active"]]
    assert len(on) == len(off) == 8 and on == off
    assert len(set(on)) > 1  # the choice variate really varies the channel


def test_airframe_effect_validation():
    assert airframe_effect_errors({"mode": "tyre_burst", "leg": "*"}) == []
    assert airframe_effect_errors({"mode": "tyre_burst", "legs": [1, 2]}) == []
    assert airframe_effect_errors({"mode": "wing_off"})
    assert airframe_effect_errors({"mode": "tyre_burst", "leg": 4})
    assert airframe_effect_errors({"mode": "tyre_burst", "legs": []})
    assert airframe_effect_errors({"mode": "tyre_burst", "legs": [1], "leg": 1})


def test_key_leg_without_a_side_suffix_is_an_error():
    sysm, _f, _h, _recs = build()
    ev = Event(SEC, "faults.inject", "faults", {"mode": "FM.LG.DOWNLOCK_FORCE", "covered": True, "key": "x"})
    with pytest.raises(ContractError, match="leg 'key'"):
        run_to(sysm, sysm.inject(sysm.start(), [ev]), 2 * SEC)
