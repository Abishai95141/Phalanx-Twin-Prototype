"""M18 maintenance world driven by injected events (operations-only world; module-boundary tests).

The events are what M02/M10/M11/M14 send in the operations protocol (README "Event protocol"); no fixture
fleet is needed here. A "quiet" configuration switches off periodic servicing and life limits so each test
isolates one mechanism; the mechanisms themselves are then switched on one at a time.
"""

from __future__ import annotations

from collections import Counter

import numpy as np
import pytest

from phalanx.core.events import Event
from phalanx.core.module import ModuleBase, ParamSet
from phalanx.core.state import Field, StateSchema, tree_digest
from phalanx.fork.builder import OpsOnlyBuilder
from phalanx.fork.session import OpsSession
from phalanx.health.protocol import plain_payload, read_payload
from phalanx.maintenance.config import load_m18_config
from phalanx.maintenance.docstate import decode_doc
from phalanx.maintenance.world import LOC_DEPOT, LOC_STOCK, FleetSpec, OpsTargets
from phalanx.orders.model import Order

NS = 1_000_000_000
H = 3600 * NS
DAY = 24 * H
EPOCH = 1_790_035_200 * NS  # 2026-09-22 00:00 UTC (05:30 IST)
BIG = 10**9


def quiet_cfg(**values):
    cfg = load_m18_config()
    k = cfg.n_servicing
    cfg = cfg.with_values(srv_interval_fh_s=(BIG,) * k, srv_interval_s=(BIG,) * k, **values)
    no_life = {
        c.code: {"life_fh": 0.0, "life_landings": 0.0, "life_streams": 0.0, "life_years": 0.0}
        for c in cfg.catalogue.classes
    }
    return cfg.with_catalogue_values(no_life)


def session(cfg=None, tails=("T01", "T02"), bases=("SUL",), tail_base=None, root=0x5EED, targets=None):
    fleet = FleetSpec(tuple(tails), tuple(bases), tuple(tail_base or [0] * len(tails)))
    b = OpsOnlyBuilder(fleet, EPOCH, m18_cfg=cfg or quiet_cfg(), targets=targets)
    return OpsSession(b, root)


def ev(t, kind, doc, target="m18"):
    return Event(int(t), kind, target, plain_payload(doc), source="test")  # AD-48.1 plain keys


def inject(s, events):
    s.world = s.system.inject(s.world, events)


def sortie_events(tail, t0, hours=1.0, sid=None):
    sid = sid or f"{tail}-{t0 // NS}"
    t1 = t0 + int(hours * 3600) * NS
    done = {
        "sortie_id": sid,
        "tail_no": tail,
        "t_takeoff": t0,
        "t_landing": t1,
        "flight_hours": hours,
        "landings": 1,
        "engine_cycles": 2.5 * hours,
        "engine_starts": 1,
        "chute_streamed": 1,
        "mission_type": "TRAINING",
        "crew_id": "P01",
        "aborted": False,
    }
    # every catalogued key (AD-44); reply_to "" = no scenario module to answer (AD-48.1 strict reads)
    launch = {"sortie_id": sid, "tail_no": tail, "reply_to": ""}
    return [ev(t0, "ops.launch", launch), ev(t1, "ops.sortie_done", done)]


def rows(s, rtype=None, tail=None):
    out = [r for r in s.records("maint.records") if rtype is None or r["record_type"] == rtype]
    return [r for r in out if tail is None or r["tail_no"] == tail]


def m18(s):
    return s.world.states["m18"]


def doc(s, name):
    return decode_doc(m18(s)[name])


def serial_at(s, tail_index, pos_code):
    cfg = s.builder.m18_cfg
    r = int(m18(s)["tail_inst"][tail_index, cfg.catalogue.pos(pos_code).index])
    return r, str(m18(s)["ser_no"][r])


def order(s, oid, action, *, tail="T01", params=None, kind="HUMAN", base=None, evidence=()):
    return Order(
        order_id=oid,
        issuer_id="TEST",
        issuer_kind=kind,
        t_issued=s.t_utc,
        t_effective=s.t_utc,
        action=action,
        parameters=params or {},
        target_tail_no=tail,
        target_base=base,
        evidence=evidence,
    )


def statuses(s, oid):
    return [
        (r["status_seq"], r["status"], r["reason"])
        for r in s.records("orders.status")
        if r["order_id"] == oid
    ]


def caution_row(tail, code, lru, rid_byte):
    return {
        "record_id": f"{rid_byte:02x}" * 16,
        "tail_no": tail,
        "sortie_id": None,
        "event_code": code,
        "suspect_lrus": [{"lru": lru, "isolation_confidence": 0.8}],
        "severity": "CAUTION",
        "displayed": True,
    }


# ------------------------------------------------------------------------------------------------ state and
# usage
@pytest.mark.unit
def test_initial_state_deterministic_and_staggered():
    cfg = load_m18_config()
    a, b, c = session(cfg, root=1), session(cfg, root=1), session(cfg, root=2)
    da, db, dc = (tree_digest(x.world.states["m18"]) for x in (a, b, c))
    assert da == db and da != dc
    st = m18(a)
    # steady-state fleet: servicing phases differ between tails; initial spares are ceil(stock_per_ac x n)
    assert not np.array_equal(st["srv_fh"][0], st["srv_fh"][1])
    n_eng_spares = int(
        np.sum((st["ser_loc"] == LOC_STOCK) & (st["ser_cls"] == cfg.catalogue.cls("ENG").index))
    )
    assert n_eng_spares == 1  # ceil(0.2 x 2)


@pytest.mark.unit
def test_sortie_record_and_usage_accrual():
    s = session()
    _, eng0 = serial_at(s, 0, "ENG")
    r_eng, _ = serial_at(s, 0, "ENG")
    tsn0 = int(m18(s)["ser_tsn"][r_eng])
    inject(s, sortie_events("T01", 3 * H, hours=1.25))
    s.run_until(1 * DAY)
    srt = rows(s, "SORTIE")
    assert len(srt) == 1
    r = srt[0]
    assert r["flight_hours"] == pytest.approx(1.25) and r["engine_serial"] == eng0
    assert r["t_close"] == EPOCH + 3 * H + int(1.25 * 3600) * NS
    assert r["t_ingest"] == r["t_close"] + 1800 * NS  # recorded 0.5 h after landing (A-W1.8-2)
    assert int(m18(s)["ser_tsn"][r_eng]) == tsn0 + 4500
    assert int(m18(s)["tail_fh"][0]) == 4500 and int(m18(s)["tail_fh"][1]) == 0


# ------------------------------------------------------------------------------------------------ defects
@pytest.mark.unit
def test_pilot_writeup_isolates_and_replaces_the_faulty_unit():
    cfg = quiet_cfg().with_catalogue_values(
        {"OBOGS": {"p_isolate": 1.0, "p_ground_repro": 1.0, "p_bench_miss": 0.0, "p_bcm": 0.0}}
    )
    s = session(cfg)
    _, sn = serial_at(s, 0, "OBOGS")
    inject(
        s,
        [
            ev(
                3 * H + 600 * NS,
                "truth.fault",
                {
                    "fault_id": "F1",
                    "tail": "T01",
                    "pos": "OBOGS",
                    "serial": sn,
                    "mode": "FM.TEST",
                    "symptom": "pilot",
                    "grounding": True,
                },
            )
        ],
    )
    inject(s, sortie_events("T01", 3 * H))
    s.run_until(10 * DAY)
    wo = rows(s, "DEFECT_WO", "T01")
    assert next(r["status"] for r in wo) == "OPEN" and wo[-1]["status"] == "CLOSED"
    assert wo[0]["when_discovered"] == "WD-AIR" and wo[0]["t_event"] == EPOCH + 4 * H + 1080 * NS
    assert wo[-1]["action_taken_code"] == "AT-RR" and wo[-1]["man_hours"] > 0
    life = rows(s, "COMPONENT_LIFE", "T01")
    moved = [(r["install_action"], r["serial_no"]) for r in life if r["job_no"] == wo[0]["job_no"]]
    assert moved[0] == ("REMOVE", sn) and moved[1][0] == "INSTALL" and moved[1][1] != sn
    sf = rows(s, "SHOP_FINDING")
    assert [(r["serial_no"], r["shop_finding"]) for r in sf] == [(sn, "CONFIRMED")]
    tl = rows(s, "TECH_LOG", "T01")
    assert [r["availability_state"] for r in tl] == ["FMC", "NMCM_U", "FMC"]


@pytest.mark.unit
def test_shop_findings_follow_truth_rtok_for_a_healthy_unit():
    """A displayed caution with no physical fault: the suspect is replaced anyway (p_replace_unconfirmed = 1)
    and the bench finds nothing (RTOK): the NFF mechanism comes from truth, not from a label."""
    s = session(quiet_cfg(p_replace_unconfirmed=1.0))
    _, sn = serial_at(s, 0, "FQGS")
    inject(
        s,
        [
            ev(
                2 * H,
                "obs.event",
                {"topic": "events.cautions", "row": caution_row("T01", "FUE-010", "ECFM_C", 1)},
            )
        ],
    )
    s.run_until(10 * DAY)
    sf = rows(s, "SHOP_FINDING")
    assert [(r["serial_no"], r["shop_finding"]) for r in sf] == [(sn, "RTOK")]
    wo = rows(s, "DEFECT_WO", "T01")
    assert wo[0]["when_discovered"] == "WD-DBF" and wo[0]["evidence_record_ids"] == ["01" * 16]


@pytest.mark.unit
def test_bit_only_nongrounding_code_is_monitored_then_admin_closed():
    s = session()
    row = caution_row("T01", "NAV-310", "INGPS", 2)
    inject(
        s, [ev(2 * H, "obs.event", {"topic": "events.bit_faults", "row": {**row, "severity": "ADVISORY"}})]
    )
    for d in range(3):
        inject(s, sortie_events("T01", (d + 1) * DAY + 4 * H))
    s.run_until(5 * DAY)
    wo = rows(s, "DEFECT_WO", "T01")
    assert (
        wo[0]["status"] == "OPEN" and wo[1]["status"] == "DEFERRED" and wo[1]["action_taken_code"] == "AT-DEF"
    )
    assert wo[-1]["status"] == "CLOSED" and wo[-1]["action_taken_code"] == "AT-ADM"
    assert {r["availability_state"] for r in rows(s, "TECH_LOG", "T01")} == {
        "FMC"
    }  # monitoring is administrative


@pytest.mark.unit
def test_recurrence_ends_monitoring_and_troubleshoots():
    s = session()
    row = {**caution_row("T01", "NAV-310", "INGPS", 3), "severity": "ADVISORY"}
    inject(
        s,
        [
            ev(2 * H, "obs.event", {"topic": "events.bit_faults", "row": row}),
            ev(DAY, "obs.event", {"topic": "events.bit_faults", "row": {**row, "record_id": "04" * 16}}),
        ],
    )
    s.run_until(4 * DAY)
    wo = rows(s, "DEFECT_WO", "T01")
    assert any("REPEAT/RECURRING" in (r["discrepancy_text"] or "") for r in wo)
    assert wo[-1]["status"] == "CLOSED" and wo[-1]["action_taken_code"] in ("AT-CND", "AT-RR")


# ------------------------------------------------------------------------------------------------ hard time
# / servicing
@pytest.mark.unit
def test_hard_time_removal_goes_to_depot_for_overhaul():
    cfg = quiet_cfg().with_catalogue_values({"AMAGB": {"life_fh": 750 * 3600.0}})
    s = session(cfg)
    r, _sn = serial_at(s, 0, "AMAGB")
    st = dict(s.world.states["m18"])
    tso = st["ser_tso"].copy()
    tso[r] = 750 * 3600
    st["ser_tso"] = tso
    s.world.states["m18"] = st
    s.run_until(3 * DAY)
    wo = rows(s, "DEFECT_WO", "T01")
    assert wo[0]["malfunction_code"] == "MAL-HT" and wo[0]["when_discovered"] == "WD-SCH"
    assert "HI-TIME" in wo[0]["discrepancy_text"]
    assert wo[-1]["status"] == "CLOSED"
    assert (
        int(m18(s)["ser_loc"][r]) == LOC_DEPOT
        and int(m18(s)["tail_inst"][0, cfg.catalogue.pos("AMAGB").index]) != r
    )


@pytest.mark.unit
def test_servicing_due_starts_at_review_and_resets_counters():
    base = load_m18_config()
    cfg = quiet_cfg().with_values(
        srv_interval_fh_s=base.srv_interval_fh_s, srv_interval_s=base.srv_interval_s
    )
    s = session(cfg)
    st = dict(s.world.states["m18"])
    last = st["srv_last"].copy()
    last[0, 0] = -100 * DAY  # SRV-L1 overdue on T01
    st["srv_last"] = last
    s.world.states["m18"] = st
    s.run_until(4 * DAY)
    insp = rows(s, "INSPECTION", "T01")
    assert insp[0]["inspection_type"] == "SRV-L1" and insp[0]["type_maint_code"] == "TM-SCH"
    # the review is the daily 08:00 IST maintenance meeting (kernel 2.5 h after the 05:30 IST epoch)
    assert insp[0]["t_open"] == EPOCH + int(2.5 * 3600) * NS
    assert insp[-1]["status"] == "CLOSED"
    assert int(m18(s)["srv_last"][0, 0]) == insp[-1]["t_close"] - EPOCH
    assert "NMCM_S" in {r["availability_state"] for r in rows(s, "TECH_LOG", "T01")}


@pytest.mark.unit
def test_inspection_finds_latent_fault():
    cfg = quiet_cfg(pod_borescope=1.0)
    s = session(cfg)
    _, sn = serial_at(s, 0, "ENG")
    inject(
        s,
        [
            ev(
                H,
                "truth.fault",
                {
                    "fault_id": "F9",
                    "tail": "T01",
                    "pos": "ENG",
                    "serial": sn,
                    "mode": "FM.TEST",
                    "symptom": "latent",
                    "grounding": True,
                },
            )
        ],
    )
    s.run_until(2 * H)
    s.submit([order(s, "ORD-INSP-1", "INSPECT", params={"type": "BORESCOPE"})])
    s.run_until(5 * DAY)
    wo = [r for r in rows(s, "DEFECT_WO", "T01") if r["malfunction_code"] == "MAL-INS"]
    assert wo and wo[0]["part_no"] == "SYN-PN-ENG-F404" and wo[0]["when_discovered"] == "WD-CND"
    assert statuses(s, "ORD-INSP-1")[-1][1] == "COMPLETED"


# ------------------------------------------------------------------------------------------------ resources
@pytest.mark.unit
def test_teams_limit_concurrency_and_jobs_queue():
    s = session(quiet_cfg(teams=2), tails=("T01", "T02", "T03", "T04"))
    evs = []
    for i, tail in enumerate(("T01", "T02", "T03", "T04")):
        row = caution_row(tail, "HYD-120", "NONE", 10 + i)
        row["suspect_lrus"] = []
        evs.append(ev(2 * H, "obs.event", {"topic": "events.cautions", "row": row}))
    inject(s, evs)
    peak = 0
    for k in range(1, 48):
        s.run_until(2 * H + k * 1800 * NS)
        busy = doc(s, "doc_res")["busy"]["SUL"]
        assert len(busy) <= 2
        peak = max(peak, len(busy))
    assert peak == 2
    assert "AWAITING_MAINTENANCE" in {r["status"] for r in rows(s, "DEFECT_WO")}


@pytest.mark.unit
def test_stock_never_exceeds_authorised_after_returns():
    """PROXY A-W1.8-17 bound: base stock of a class never exceeds its authorised level, even as healthy units
    return from the shop and backorder deliveries arrive (n = 4 R/R orders, one class)."""
    s = session(tails=("T01", "T02", "T03", "T04"))
    cfg = s.builder.m18_cfg
    ci = cfg.catalogue.cls("RADAR").index
    authorised = 1  # ceil(0.1 x 4)
    s.run_until(H)
    s.submit(
        [
            order(s, f"ORD-RR-{t}", "REMOVE_REPLACE", tail=t, params={"position": "RADAR"})
            for t in ("T01", "T02", "T03", "T04")
        ]
    )
    for k in range(1, 400):
        s.run_until(H + k * 6 * H)
        st = m18(s)
        stock = int(np.sum((st["ser_loc"] == LOC_STOCK) & (st["ser_cls"] == ci) & (st["ser_alloc"] == "")))
        assert stock <= authorised
    assert {r["shop_finding"] for r in rows(s, "SHOP_FINDING")} == {"RTOK"}
    assert all(statuses(s, f"ORD-RR-{t}")[-1][1] == "COMPLETED" for t in ("T01", "T02", "T03", "T04"))


# ------------------------------------------------------------------------------------------------ orders (A1
# rules)
@pytest.mark.unit
def test_release_with_open_grounding_defect_is_rejected_and_ground_release_round_trip():
    s = session()
    s.run_until(H)
    s.submit([order(s, "G1", "GROUND", params={"reason": "fleet check"})])
    s.run_until(DAY)
    assert rows(s, "TECH_LOG", "T01")[-1]["availability_state"] == "NMCM_U"
    s.submit([order(s, "R1", "RELEASE")])
    s.run_until(2 * DAY)
    assert rows(s, "TECH_LOG", "T01")[-1]["availability_state"] == "FMC"
    assert [x[1] for x in statuses(s, "R1")] == ["ACCEPTED", "COMPLETED"]
    # an open grounding defect blocks release (airworthiness)
    inject(
        s,
        [
            ev(
                2 * DAY + H,
                "obs.event",
                {"topic": "events.cautions", "row": caution_row("T02", "HYD-120", "X", 9)},
            ),
            ev(2 * DAY + H, "truth.incident", {"tail": "T02", "kind": "excursion", "positions": ["TYR_L"]}),
        ],
    )
    s.run_until(2 * DAY + 2 * H)
    s.submit([order(s, "R2", "RELEASE", tail="T02")])
    s.run_until(3 * DAY)
    st = statuses(s, "R2")
    assert st[-1][1] == "REJECTED" and "open grounding defect" in st[-1][2]


@pytest.mark.unit
def test_defer_rules_and_expiry():
    s = session()
    inject(
        s,
        [ev(H, "obs.event", {"topic": "events.cautions", "row": caution_row("T01", "AVI-520", "RADAR", 5)})],
    )
    s.run_until(2 * H)
    job = rows(s, "DEFECT_WO", "T01")[0]["job_no"]
    # RADAR is MESM 'P' (non-grounding) but a pilot caution is troubleshot now; defer the open job
    s.submit(
        [order(s, "D1", "DEFER", params={"job_no": job, "limits": "NO RADAR MISSIONS", "expiry_hours": 48})]
    )
    s.run_until(DAY)
    st = statuses(s, "D1")
    assert st[-1][1] in ("COMPLETED", "REJECTED")
    inject(s, [ev(DAY + H, "truth.incident", {"tail": "T02", "kind": "excursion", "positions": ["TYR_R"]})])
    s.run_until(DAY + 2 * H)
    gjob = rows(s, "DEFECT_WO", "T02")[0]["job_no"]
    s.submit(
        [order(s, "D2", "DEFER", tail="T02", params={"job_no": gjob, "limits": "X", "expiry_hours": 10})]
    )
    s.run_until(3 * DAY)
    assert statuses(s, "D2")[-1][1:] == ("REJECTED", "a grounding defect cannot be deferred")


@pytest.mark.unit
def test_cannibalise_validation_and_execution():
    cfg = quiet_cfg().with_catalogue_values(
        {"GEN": {"stock_per_ac": 0.0, "p_isolate": 1.0, "p_ground_repro": 1.0}}
    )
    s = session(cfg, tails=("T01", "T02", "T03"))
    _, sn1 = serial_at(s, 0, "GEN")
    inject(
        s,
        [
            ev(
                H,
                "truth.fault",
                {
                    "fault_id": "F1",
                    "tail": "T01",
                    "pos": "GEN",
                    "serial": sn1,
                    "mode": "FM.TEST",
                    "symptom": "preflight",
                    "grounding": True,
                },
            ),
            ev(H, "ops.ground_abort", {"tail_no": "T01", "sortie_id": "x"}),
            ev(H, "truth.incident", {"tail": "T02", "kind": "excursion", "positions": ["TYR_L"]}),
        ],
    )
    s.run_until(DAY + 2 * H)
    awp = [r for r in rows(s, "DEFECT_WO", "T01") if r["status"] == "AWAITING_PARTS"]
    assert awp, "T01 should be awaiting a generator (no spares)"
    job = awp[0]["job_no"]
    s.submit(
        [
            order(s, "C0", "CANNIBALISE", params={"job_no": job, "donor_tail_no": "T01"}),
            order(s, "C1", "CANNIBALISE", params={"job_no": job, "donor_tail_no": "T09"}),
        ]
    )
    s.run_until(2 * DAY)
    assert statuses(s, "C0")[-1][1] == "REJECTED" and statuses(s, "C1")[-1][1] == "REJECTED"
    s.submit([order(s, "C2", "CANNIBALISE", params={"job_no": job, "donor_tail_no": "T03"})])
    s.run_until(4 * DAY)
    cn = rows(s, "CANNIBALISATION")
    assert {r["donor_tail_no"] for r in cn} == {"T03"}
    assert any(r["tail_no"] == "T01" and r["action_taken_code"] == "AT-CNI" for r in cn)
    assert rows(s, "DEFECT_WO", "T01")[-1]["status"] == "CLOSED"
    assert rows(s, "TECH_LOG", "T03")[-1]["availability_state"] == "NMCS"  # the donor now waits for the part
    assert [x[1] for x in statuses(s, "C2")] == ["ACCEPTED", "QUEUED", "IN_WORK", "COMPLETED"]


@pytest.mark.unit
def test_supply_orders_requisition_expedite_transfer():
    s = session(tails=("T01", "T02"), bases=("SUL", "NAL"), tail_base=[0, 1])
    s.run_until(H)
    s.submit(
        [
            Order(
                "Q1",
                "TEST",
                "HUMAN",
                s.t_utc,
                s.t_utc,
                "REQUISITION_SPARES",
                {"part_no": "SYN-PN-TYRE", "quantity": 2},
                priority="PHU",
                target_base="SUL",
            )
        ]
    )
    s.run_until(DAY)
    dem = [r for r in rows(s, "SUPPLY_DEMAND") if r["order_id"] == "Q1"]
    assert len({r["demand_no"] for r in dem}) == 2 and all(r["priority"] == "PHU" for r in dem)
    dn = dem[0]["demand_no"]
    s.submit(
        [
            Order(
                "E1",
                "TEST",
                "HUMAN",
                s.t_utc,
                s.t_utc,
                "EXPEDITE_SPARES",
                {"demand_no": dn},
                target_base="SUL",
            )
        ]
    )
    s.submit(
        [
            Order(
                "X1",
                "TEST",
                "HUMAN",
                s.t_utc,
                s.t_utc,
                "TRANSFER_STOCK",
                {"part_no": "SYN-PN-TYRE", "quantity": 1, "from_base": "SUL", "to_base": "NAL"},
                target_base="SUL",
            )
        ]
    )
    s.run_until(4 * DAY)  # applied at the next 08:00 IST epoch, then 2 days in transit
    assert statuses(s, "E1")[-1][1] == "COMPLETED" and statuses(s, "X1")[-1][1] == "COMPLETED"
    st = m18(s)
    ci = s.builder.m18_cfg.catalogue.cls("TYRE").index
    assert int(np.sum((st["ser_loc"] == LOC_STOCK) & (st["ser_cls"] == ci) & (st["ser_base"] == 1))) == 1 + 6
    s.run_until(400 * DAY)
    assert statuses(s, "Q1")[-1][1] == "COMPLETED"


class CatchAll(ModuleBase):
    """TEST FIXTURE: an event-only neighbour that accepts every event (stands in for M10/M14 here)."""

    version = "1.0.0"
    rate = None
    state_schema = StateSchema("test.catchall", 1, (Field("n", "<i8"),))

    def __init__(self, id: str) -> None:
        super().__init__(id, ParamSet("test.catchall", {}))

    def init(self, params, keys):
        return {"n": np.array(0, dtype=np.int64)}

    def initial_outputs(self, state):
        return {}

    def on_event(self, state, event, t):
        return state, []


@pytest.mark.unit
def test_servicing_extension_cap_mods_software_and_monitoring_filters():
    base = load_m18_config()
    cfg = quiet_cfg().with_values(
        srv_interval_fh_s=base.srv_interval_fh_s, srv_interval_s=base.srv_interval_s
    )
    s = session(cfg, targets=OpsTargets(m21="m21", sink="sink", health=None, monitoring=None))
    s.run_until(H)
    s.submit(
        [
            order(s, "S1", "DEFER_SERVICING", params={"servicing": "SRV-L2-MINOR", "extend_hours": 5.0}),
            order(s, "S2", "DEFER_SERVICING", params={"servicing": "SRV-L2-MINOR", "extend_hours": 500.0}),
            order(
                s, "M1", "EMBODY_MODIFICATION", base="SUL", tail=None, params={"mod_id": "MOD-FQGS-PICKUP"}
            ),
            order(s, "W1", "LOAD_SOFTWARE", params={"sw_config_id": "SW-BRK-Y"}),
            order(s, "F1", "CHANGE_MONITORING_CONFIG", params={"filter_codes_add": ["NAV-310"]}),
            order(s, "A1", "ASSIGN_SORTIE", params={"date": "2026-09-23", "sorties": 2}),
        ]
    )
    s.run_until(3 * DAY)
    assert statuses(s, "S1")[-1][1] == "COMPLETED"
    assert statuses(s, "S2")[-1][1] == "REJECTED" and "exceeds" in statuses(s, "S2")[-1][2]
    mods = rows(s, "MODIFICATION")
    assert {r["compliance_status"] for r in mods if r["status"] == "OPEN"} == {"ISSUED"}
    assert Counter(
        r["tail_no"] for r in mods if r["compliance_status"] == "COMPLIED" and r["order_id"] == "M1"
    ) == {"T01": 1, "T02": 1}
    assert [r["sw_config_id"] for r in rows(s, "MODIFICATION", "T01") if r["order_id"] == "W1"][
        -1
    ] == "SW-BRK-Y"
    assert statuses(s, "A1")[-1][1] == "REJECTED"  # T01 is down for the mod/software work, or no M02 here
    # a filtered code no longer raises a snag
    row = {**caution_row("T01", "NAV-310", "INGPS", 7), "severity": "ADVISORY"}
    inject(s, [ev(3 * DAY + H, "obs.event", {"topic": "events.bit_faults", "row": row})])
    s.run_until(4 * DAY)
    assert not [r for r in rows(s, "DEFECT_WO", "T01") if "NAV-310" in (r["discrepancy_text"] or "")]


@pytest.mark.unit
def test_wash_and_inspect_orders_emit_actions_to_the_health_module():
    targets = OpsTargets(m21="m21", sink="sink", health="hsink")
    fleet = FleetSpec(("T01",), ("SUL",), (0,))
    b = OpsOnlyBuilder(fleet, EPOCH, m18_cfg=quiet_cfg(), targets=targets, extra=(lambda: CatchAll("hsink"),))
    s = OpsSession(b, 7)
    s.run_until(H)
    s.submit([order(s, "WASH1", "WASH_SERVICE", params={"type": "ENGINE_WASH"})])
    _, trace = s.system.run(s.world, 2 * 240 * 86_400)  # the kernel trace shows events to non-record targets
    actions = [read_payload(e.payload) for _, e in trace.dispatched if e.target == "hsink"]
    assert any(a.get("action") == "ENGINE_WASH" and a.get("tail") == "T01" for a in actions)
    s.run_until(2 * DAY)
    assert statuses(s, "WASH1")[-1][1] == "COMPLETED"
    insp = rows(s, "INSPECTION", "T01")
    assert insp[-1]["inspection_type"] == "WASH" and insp[-1]["status"] == "CLOSED"
