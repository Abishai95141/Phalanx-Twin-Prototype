"""A-W1.8-6 exposing test: troubleshooting outcomes follow the diagnosis parameters, and NFF/RTOK comes from
truth (the bench finds nothing on a healthy unit removed by misdiagnosis).

Design: every tail gets one real, pilot-reported grounding fault on hydraulic pump 1 (ambiguity group
HYDRAULIC = {HYDP1, HYDP2}) and flies one sortie; spares are plentiful and the bench never misses, so the
first troubleshooting decision of each work order is observed directly in the records. Expected shares
(p_ground_repro = 0.85, p_isolate = 0.8, p_replace_unconfirmed = 0): right unit removed 0.68, wrong unit
removed 0.17, could-not-duplicate 0.15.

Sample size (fixed before running): n = 150 work orders (150 tails at 5 bases, one fault each; per-tail
streams make them independent). The binomial standard error is <= 0.041 for each share; the test is a
chi-square goodness of fit (df = 2) at alpha = 0.01.
"""

from __future__ import annotations

import pytest
from scipy.stats import chisquare

from phalanx.core.events import Event
from phalanx.fork.builder import OpsOnlyBuilder
from phalanx.fork.session import OpsSession
from phalanx.health.protocol import plain_payload
from phalanx.maintenance.config import load_m18_config
from phalanx.maintenance.world import FleetSpec

NS = 1_000_000_000
H = 3600 * NS
DAY = 24 * H
EPOCH = 1_790_035_200 * NS
BIG = 10**9
N_BASES, PER_BASE = 5, 30


def _ev(t, kind, doc):
    return Event(int(t), kind, "m18", plain_payload(doc), source="test")  # AD-48.1 plain keys


@pytest.mark.statistical
def test_troubleshooting_outcomes_match_the_diagnosis_parameters_and_rtok_follows_truth():
    cfg = load_m18_config()
    k = cfg.n_servicing
    cfg = cfg.with_values(srv_interval_fh_s=(BIG,) * k, srv_interval_s=(BIG,) * k, p_replace_unconfirmed=0.0)
    no_life = {
        c.code: {"life_fh": 0.0, "life_landings": 0.0, "life_streams": 0.0, "life_years": 0.0}
        for c in cfg.catalogue.classes
    }
    hydp = {"p_ground_repro": 0.85, "p_isolate": 0.8, "p_bench_miss": 0.0, "p_bcm": 0.0, "stock_per_ac": 2.0}
    cfg = cfg.with_catalogue_values({**no_life, "HYDP": {**no_life["HYDP"], **hydp}})
    assert cfg.catalogue.ambiguity_group(cfg.catalogue.pos("HYDP1").index) == (
        cfg.catalogue.pos("HYDP1").index,
        cfg.catalogue.pos("HYDP2").index,
    )
    tails = tuple(f"T{i:03d}" for i in range(N_BASES * PER_BASE))
    bases = tuple(f"B{j}" for j in range(N_BASES))
    fleet = FleetSpec(tails, bases, tuple(i // PER_BASE for i in range(len(tails))))
    s = OpsSession(OpsOnlyBuilder(fleet, EPOCH, m18_cfg=cfg), 0x0A6)
    st = s.world.states["m18"]
    p1 = cfg.catalogue.pos("HYDP1").index
    faulty = {tn: str(st["ser_no"][int(st["tail_inst"][i, p1])]) for i, tn in enumerate(tails)}
    events = []
    for tn in tails:
        sid = f"{tn}-S1"
        events += [
            _ev(
                H,
                "truth.fault",
                {
                    "fault_id": f"F-{tn}",
                    "tail": tn,
                    "pos": "HYDP1",
                    "serial": faulty[tn],
                    "mode": "FM.TEST",
                    "symptom": "pilot",
                    "grounding": True,
                },
            ),
            _ev(3 * H, "ops.launch", {"sortie_id": sid, "tail_no": tn, "reply_to": ""}),
            _ev(
                4 * H,
                "ops.sortie_done",
                {
                    "sortie_id": sid,
                    "tail_no": tn,
                    "t_takeoff": 3 * H,
                    "t_landing": 4 * H,
                    "flight_hours": 1.0,
                    "landings": 1,
                    "engine_cycles": 2.5,
                    "engine_starts": 1,
                    "chute_streamed": 1,
                    "mission_type": "TRAINING",
                    "crew_id": "P01",
                    "aborted": False,
                },
            ),
        ]
    s.world = s.system.inject(s.world, events)
    s.run_until(40 * DAY)  # troubleshooting within a day; base-shop turnaround 5 d median
    recs = s.records("maint.records")
    wo = {}
    for r in recs:
        if r["record_type"] == "DEFECT_WO" and r["when_discovered"] == "WD-AIR":
            wo.setdefault(r["tail_no"], r["job_no"])
    assert set(wo) == set(tails), "every fault is written up once"
    first_removal = {}
    for r in recs:
        if r["record_type"] == "COMPONENT_LIFE" and r["install_action"] == "REMOVE":
            if r["job_no"] == wo.get(r["tail_no"]):
                first_removal.setdefault(r["tail_no"], r["serial_no"])
    closed_cnd = {
        r["tail_no"]
        for r in recs
        if r["record_type"] == "DEFECT_WO" and r["status"] == "CLOSED" and r["action_taken_code"] == "AT-CND"
    }
    right = sum(1 for tn in tails if first_removal.get(tn) == faulty[tn])
    wrong = sum(1 for tn in tails if tn in first_removal and first_removal[tn] != faulty[tn])
    cnd = sum(1 for tn in tails if tn not in first_removal)
    assert cnd == len(closed_cnd & set(tails)), "every unreproduced report is closed could-not-duplicate"
    n = len(tails)
    expected = [0.68 * n, 0.17 * n, 0.15 * n]
    stat, p = chisquare([right, wrong, cnd], expected)
    assert p > 0.01, (right, wrong, cnd, stat, p)
    # NFF/RTOK from truth: wrongly removed (healthy) pumps are RTOK at the bench, faulty ones CONFIRMED
    finding = {r["serial_no"]: r["shop_finding"] for r in recs if r["record_type"] == "SHOP_FINDING"}
    removed = set(first_removal.values())
    assert removed <= set(finding), "every removed pump reaches the shop within the window"
    for tn, sn in first_removal.items():
        assert finding[sn] == ("CONFIRMED" if sn == faulty[tn] else "RTOK"), (tn, sn)
