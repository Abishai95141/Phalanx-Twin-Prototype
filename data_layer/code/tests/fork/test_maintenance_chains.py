"""Event chains of architecture §10 / report §12, end to end on the fixture fleet.

Sample: n = 1 short run per chain (2-4 tails, 20-40 days, fixed seed); each test asserts the documented
sequence of records, so one occurrence answers it.

Chains 1 (anomaly -> R/R -> shop), 4 (servicing) and 5 (hard time) are covered by the M18 unit tests
(``test_pilot_writeup_isolates_and_replaces_the_faulty_unit``, ``test_shop_findings_follow_truth_rtok_...``,
``test_servicing_due_starts_at_review_...``, ``test_hard_time_removal_goes_to_depot_for_overhaul``). Here:
2 (BIT false alarm: monitor, then admin close or troubleshoot), 3 (exceedance -> conditional inspection,
aircraft down), 6 (Tejas JFS start failure), 7 (Tejas brake software -> excursion -> fleet grounding ->
corrected load -> staged release) and 8 (Tejas gauging artefact -> CND -> modification removes it).
"""

from __future__ import annotations

from dataclasses import replace

import pytest
from test_fork_fixture_fleet import DAY, EPOCH, FixtureFleetBuilder, FixtureParams

from phalanx.fork.session import OpsSession
from phalanx.orders.model import Order


def _rows(s, rtype, tail=None):
    return [
        r
        for r in s.records("maint.records")
        if r["record_type"] == rtype and (tail is None or r["tail_no"] == tail)
    ]


def _order(s, oid, action, params, *, tail=None, base=None):
    return Order(
        oid, "AIRHQ", "HUMAN", s.t_utc, s.t_utc, action, params, target_tail_no=tail, target_base=base
    )


@pytest.mark.fork
def test_chain_2_bit_false_alarm_is_monitored_and_closed_or_troubleshot():
    p = replace(FixtureParams(), fa_per_fh=1.0, fa_codes=("NAV-310",))  # non-grounding INGPS code
    b = FixtureFleetBuilder(n_tails=3, horizon_days=30, p=p)
    s = OpsSession(b, 0x0C2)
    s.run_until(30 * DAY)
    wo = [r for r in _rows(s, "DEFECT_WO") if "NAV-310" in (r["discrepancy_text"] or "")]
    assert any(r["status"] == "DEFERRED" and r["action_taken_code"] == "AT-DEF" for r in wo)
    closes = {r["action_taken_code"] for r in wo if r["status"] == "CLOSED"}
    assert closes & {"AT-ADM", "AT-CND", "AT-RR"}
    assert any(r["when_discovered"] == "WD-HMS" and r["evidence_record_ids"] for r in wo)


@pytest.mark.fork
def test_chain_3_exceedance_grounds_until_the_conditional_inspection():
    p = replace(FixtureParams(), p_exceed_per_sortie=0.5)
    b = FixtureFleetBuilder(n_tails=3, horizon_days=20, p=p)
    s = OpsSession(b, 0x0C3)
    s.run_until(20 * DAY)
    ei = _rows(s, "EXCEEDANCE_INSPECTION")
    assert ei, "exceedances are written up as conditional inspections"
    first = next(r for r in ei if r["record_version"] == 0)
    assert first["when_discovered"] == "WD-CND" and first["evidence_record_ids"]
    tl = [r for r in _rows(s, "TECH_LOG", first["tail_no"]) if r["t_event"] >= first["t_event"]]
    assert tl[0]["availability_state"] == "NMCM_U" and first["record_key"] in tl[0]["limitations_text"]
    assert any(r["record_key"] == first["record_key"] and r["status"] == "CLOSED" for r in ei)


@pytest.mark.fork
def test_chain_6_jfs_start_failure_aborts_the_sortie_and_raises_a_preflight_snag():
    w = dict(FixtureParams().weibull)
    w["JFS"] = (1.0, 3.0)  # a starter that fails within a few hours
    b = FixtureFleetBuilder(n_tails=2, horizon_days=20, p=replace(FixtureParams(), weibull=w))
    s = OpsSession(b, 0x0C6)
    s.run_until(20 * DAY)
    wo = [r for r in _rows(s, "DEFECT_WO") if r["malfunction_code"] == "MAL-STR"]
    assert wo and wo[0]["when_discovered"] == "WD-PRE" and "START FAILED" in wo[0]["discrepancy_text"]
    assert any(
        r["record_key"] == wo[0]["record_key"] and r["status"] == "CLOSED" for r in _rows(s, "DEFECT_WO")
    )


@pytest.mark.fork
def test_chain_7_brake_software_excursion_fleet_grounding_and_staged_release():
    p = replace(FixtureParams(), p_brake_incident=0.5)
    b = FixtureFleetBuilder(n_tails=4, horizon_days=40, p=p)
    s = OpsSession(b, 0x0C7)
    s.run_until(b.calendar.next_epoch(DAY))
    s.submit([_order(s, "SW-X", "LOAD_SOFTWARE", {"sw_config_id": "SW-BRK-X"}, base="SUL")])
    s.run_until(8 * DAY)
    exc = [r for r in _rows(s, "DEFECT_WO") if r["malfunction_code"] == "MAL-DMG"]
    assert exc and exc[0]["when_discovered"] == "WD-ABT"
    # the engineering authority grounds the fleet, clears a corrected load and releases tails in stages
    s.run_until(b.calendar.next_epoch(8 * DAY))
    s.submit([_order(s, "GRD-FLEET", "GROUND", {"reason": "brake software"}, base="SUL")])
    s.run_until(b.calendar.next_epoch(9 * DAY))
    # every tail carries the order in its tech log and is not mission capable (NMCM-U, or worse if it was
    # already awaiting parts: SCIR precedence)
    held = [r for r in _rows(s, "TECH_LOG") if "GROUNDED BY ORDER" in (r["limitations_text"] or "")]
    assert {r["tail_no"] for r in held} == set(b.tails)
    assert {r["availability_state"] for r in held} <= {"NMCM_U", "NMCS", "NMCD"}
    s.submit([_order(s, "SW-FIX", "LOAD_SOFTWARE", {"sw_config_id": "SW-BRK-Y"}, base="SUL")])
    s.run_until(b.calendar.next_epoch(12 * DAY))
    s.submit([_order(s, f"REL-{t}", "RELEASE", {"reason": "cleared"}, tail=t) for t in b.tails[:2]])
    s.run_until(b.calendar.next_epoch(14 * DAY))
    s.submit([_order(s, f"REL-{t}", "RELEASE", {"reason": "cleared"}, tail=t) for t in b.tails[2:]])
    s.run_until(30 * DAY)
    st = {}
    for r in s.records("orders.status"):
        st[r["order_id"]] = r["status"]
    assert st["GRD-FLEET"] == "COMPLETED" and st["SW-FIX"] == "COMPLETED"
    t_fix = max(r["t_close"] for r in _rows(s, "MODIFICATION") if r["order_id"] == "SW-FIX" and r["t_close"])
    new_wo = [
        r for r in _rows(s, "DEFECT_WO") if r["malfunction_code"] == "MAL-DMG" and r["record_version"] == 0
    ]
    assert all(r["t_event"] < t_fix for r in new_wo), "no new brake incidents after the corrected load"
    assert t_fix < EPOCH + 13 * DAY
    released = [k for k, v in st.items() if k.startswith("REL-")]
    assert len(released) == 4 and all(st[k] in ("COMPLETED", "REJECTED") for k in released)
    mods = [
        r
        for r in _rows(s, "MODIFICATION")
        if r["order_id"] == "SW-FIX" and r["compliance_status"] == "COMPLIED"
    ]
    assert {r["sw_config_id"] for r in mods} == {"SW-BRK-Y"} and len(mods) == 4


@pytest.mark.fork
def test_chain_8_gauging_artefact_until_the_modification():
    p = replace(FixtureParams(), p_gauging_premod=0.3)
    b = FixtureFleetBuilder(n_tails=3, horizon_days=40, p=p)
    s = OpsSession(b, 0x0C8)
    s.run_until(b.calendar.next_epoch(10 * DAY))
    pre = [
        r
        for r in _rows(s, "DEFECT_WO")
        if r["record_version"] == 0 and r["when_discovered"] == "WD-DBF" and r["system_code"] == "FUE"
    ]
    assert pre, "false low-fuel cautions are written up before the modification"
    s.submit([_order(s, "MOD-GAUGE", "EMBODY_MODIFICATION", {"mod_id": "MOD-FQGS-PICKUP"}, base="SUL")])
    s.run_until(14 * DAY)
    t_mod = max(
        r["t_close"] for r in _rows(s, "MODIFICATION") if r["order_id"] == "MOD-GAUGE" and r["t_close"]
    )
    s.run_until(40 * DAY)
    post = [r for r in s.records("events.cautions") if r["t_occurrence"] > t_mod]
    assert not post, "the pick-up/vent modification removes the artefact"
    closes = {
        r["action_taken_code"]
        for r in _rows(s, "DEFECT_WO")
        if r["system_code"] == "FUE" and r["status"] == "CLOSED"
    }
    assert closes & {"AT-CND", "AT-RR"}
