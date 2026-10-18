"""A5: the runtime event-protocol validator (W2.1 deliverable 3) on dispatched events.

- Negative controls: planted malformed events are caught with the right rule, including E1's surviving mutant
  m06b (M18 ``mx.action`` with ``tail`` renamed ``tail_no``), a ``{"doc": ...}`` payload (AD-48.1), a missing
  key, a wrong producer and consumer, an uncatalogued cross-module kind and an unknown source; and a planted
  event dispatched by a running System raises in strict mode.
- A real telemetry window (first gate sortie, 20 s from post-start idle, n = 1) dispatches catalogued
  cross-module kinds with zero violations.
- The tracked and internal entries are not stale against the catalogue.
- Slow: zero violations over 1 sortie and then 5 sorties (gate plan order); each run until its window end or a
  physical-invariant abort (``SortieAborted``; the flight blockers are reported), with the number of checked
  events stated.
"""

from __future__ import annotations

import fnmatch

import pytest

from phalanx.core.events import Event
from phalanx.integration.flights import diverse_sorties, fly
from phalanx.integration.plans import gate_sorties
from phalanx.integration.sortie import SortieRunner
from phalanx.integration.system import M_ID, SortieSpec, build_sortie_system
from phalanx.integration.validate import (
    INTERNAL_PROTOCOLS,
    TRACKED,
    EventProtocolError,
    EventValidator,
)

pytestmark = pytest.mark.integration

M_OF = {**M_ID, "maint": "M18", "orders": "M21"}


def _rules(v: EventValidator, ev: Event) -> set[str]:
    return {x.rule for x in v.check(ev)}


def test_planted_malformed_events_are_caught():
    v = EventValidator(M_OF, strict=False)
    ok_mx = {"tail": "TJ212", "action": "SWLOAD", "pos": "", "serial": "", "sw_config_id": ""}
    assert _rules(v, Event(0, "mx.action", "monitor", ok_mx, source="maint")) == set()
    # E1 mutant m06b: M18 mx.action key tail -> tail_no (survived make check at E1)
    m06b = {**{k: x for k, x in ok_mx.items() if k != "tail"}, "tail_no": "TJ212"}
    assert _rules(v, Event(0, "mx.action", "monitor", m06b, source="maint")) == {"payload"}
    doc = {"doc": '{"tail": "TJ212", "action": "SWLOAD"}'}
    assert _rules(v, Event(0, "mx.action", "health", doc, source="maint")) == {"encoding", "payload"}
    fault = {
        "engine": 0,
        "code": "ENG-013",
        "set": True,
        "sensor": "T1",
        "lane": "A",
        "description": "x",
        "t_frame_ns": 0,
        "frame": 1,
    }
    assert _rules(v, Event(0, "fadec.fault", "monitor", fault, source="fadec")) == set()
    no_code = {k: x for k, x in fault.items() if k != "code"}
    assert _rules(v, Event(0, "fadec.fault", "monitor", no_code, source="fadec")) == {"payload"}
    assert _rules(v, Event(0, "fadec.fault", "monitor", fault, source="monitor")) == set()  # M14 -> M14: same
    assert _rules(v, Event(0, "fadec.fault", "monitor", fault, source="fcs")) == {"producer"}
    assert _rules(v, Event(0, "fadec.fault", "health", fault, source="fadec")) == {"consumer"}
    assert _rules(v, Event(0, "fadec.private", "monitor", {}, source="fadec")) == {"uncatalogued"}
    assert _rules(v, Event(0, "fadec.fault", "monitor", fault, source="nobody")) == {"source"}
    assert _rules(v, Event(0, "fadec.private", "fadec", {}, source="fadec")) == set()  # self-event: free
    assert len(v.violations) == 8  # the doc-encoded payload counts twice (encoding + missing keys)


@pytest.fixture(scope="module")
def ss():
    return build_sortie_system(SortieSpec(plan=gate_sorties()[0], scenario="gate", root=0xA5, fused=True))


def test_zero_violations_on_a_telemetry_window_and_strict_dispatch_check(ss):
    r = SortieRunner(ss, validate_events=True)
    st = r.begin()
    st, _ = r.run(st, 20 * 240)
    assert r.validator.violations == []
    seen = {(k, p, c) for (k, p, c) in r.validator.seen}
    for need in (
        ("af.ground_elevation", "M02", "M06"),
        ("ops.power_up", "M02", "M05"),  # PBIT at the power-up (A-W2.1-11), no fcs.pbit_start
        ("ops.power_up", "M02", "M11"),
        ("ops.power_up", "M02", "M14"),
        ("monitor.observe", "M13", "M14"),
        ("scenario.sortie_plan", "M02", "M04"),
    ):
        assert need in seen, (need, sorted(seen))
    # a planted malformed event dispatched by the running System is caught at dispatch (strict mode)
    bad = Event(
        st.world.t_ns, "mx.action", "monitor", {"tail_no": "TJ212", "action": "SWLOAD"}, source="maint"
    )
    r.validator.m_of = {**r.validator.m_of, "maint": "M18"}
    st.world.queue.push(bad)
    with pytest.raises(EventProtocolError, match=r"\[payload\] mx.action maint->monitor"):
        r.run(st, 240)


def test_tracked_and_internal_entries_are_not_stale():
    """A tracked kind that becomes catalogued (W2.1c AD-49) must leave TRACKED; internal patterns never
    shadow a catalogued kind."""
    v = EventValidator(M_OF)
    for tr in TRACKED:
        assert tr.kind not in v.catalogue, f"{tr.kind} is catalogued now: remove it from TRACKED"
    for ip in INTERNAL_PROTOCOLS:
        shadow = [k for k in v.catalogue if fnmatch.fnmatchcase(k, ip.kinds)]
        assert not shadow, (ip.kinds, shadow)


@pytest.mark.slow
@pytest.mark.parametrize("n_sorties", [1, 5])
def test_zero_violations_over_sorties(n_sorties):
    """The first ``n_sorties`` of the mission-type-diverse gate sample, each from post-start idle to its
    window end or to a physical-invariant abort (``phalanx.integration.flights``, shared with A6/A10); zero
    violations; the counts of checked events and of flown seconds are reported."""
    checked = 0
    flown = 0.0
    for plan in diverse_sorties(n_sorties):
        f = fly(plan)
        if f.abort is not None:
            print(f"{f.sortie_id}: aborted at {f.flown_s:.0f} s ({f.abort_phase}): {f.abort}")
        assert f.violations == []
        # one sortie.manifest per flown sortie (shared flights): its take-off is the realised lift-off
        m = f.manifest.to_pylist()
        assert len(m) == 1 and m[0]["sortie_id"] == f.sortie_id
        if f.liftoff_s is not None:
            assert m[0]["t_takeoff"] - m[0]["t_start"] == round(f.liftoff_s * 240) * 1_000_000_000 // 240
        checked += f.checked_events
        flown += f.flown_s
    print(f"n_sorties={n_sorties}: {checked} cross-module events checked over {flown:.0f} s, 0 violations")
    assert checked > 0


def test_m08_fault_codes_are_m14_bit_codes():
    """Every code M08 can emit (``fadec.codes.FAULT_CODES``) is a dictionary ``bit_codes`` entry, which M14
    requires of every ``fadec.fault`` / ``fadec.caution`` it receives (static check of the two tables; the
    W2.1a-reported mismatch ENG-013/015/016/021/022/023/025/026/507 is closed on main since the W2.2
    merge)."""
    from phalanx.dictionary import load_dictionary
    from phalanx.fadec.codes import FAULT_CODES

    bit = {str(k) for k in load_dictionary().code_table("bit_codes")["codes"]}
    missing = sorted({f.code for f in FAULT_CODES} - bit)
    assert missing == [], missing
