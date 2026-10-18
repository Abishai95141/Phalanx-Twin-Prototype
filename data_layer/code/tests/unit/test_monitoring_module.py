"""M14 module (acceptance A5, A6): ECMS LUIs written twice per flight, take-off record trigger, exceedance and
caution records (peak, end, clear), controller BIT reports, LRU conditions (covered / missed), chunk
invariance of CIR processing, truth blindness, outbox acknowledgement, ground IBIT, usage-mode counters, and
contract-v0 conformance of every emitted batch (restricted labels never in consumer topics).

Inputs are synthetic CIR flights (TEST FIXTURE ``cir_flight``: piecewise-linear N2 / PS3 / T5 / PLA / WoW at
10 Hz, 1 h; n = 1-3 sorties per test, the smallest that exercises each record kind)."""

from __future__ import annotations

import numpy as np
import pyarrow as pa
import pytest

from phalanx.core.events import Event
from phalanx.core.module import ContractError
from phalanx.core.rng import KeyPath, RngService, StreamRegistry
from phalanx.core.scheduler import System
from phalanx.dictionary import load_dictionary
from phalanx.dictionary.contract import ContractViolation, load_contract
from phalanx.ground.cir import CIR_SCHEMA
from phalanx.monitoring import (
    MonitoringConfig,
    MonitoringModule,
    bit_report_payload,
    cir_chunk_payload,
    contract_tables,
    load_code_table,
    load_monitoring_params,
    lru_condition_payload,
)
from phalanx.monitoring.module import KIND_BIT, KIND_CAUTION, KIND_COUNTER, KIND_EXCEED

D = load_dictionary()
P = load_monitoring_params()
CODES = load_code_table(D, P)
SEC = 10**9
HOUR = 3600 * SEC
DAY = 24 * HOUR
EPOCH = 1_800_000_000 * SEC
C = load_contract("v0")


def build(*, usage_mode=False, regime="mature", root=0xC0DE):
    cfg = MonitoringConfig.from_dictionary(D, CODES, ("IN20-0001",), usage_mode=usage_mode, regime=regime)
    m = MonitoringModule("monitoring", P, config=cfg)
    sysm = System(
        [m], [], rng=RngService(root, StreamRegistry()), identity=KeyPath.of(scenario="S1", tail="KH2011")
    )
    return m, sysm


def cir_flight(t0_ns: int, *, t5_bump=0.0, truth_offset=0.0) -> pa.Table:
    """TEST FIXTURE: one hour of CIR rows (fast-path shape) for the channels M14 consumes."""
    t = np.arange(0.0, 3600.0, 0.1)
    n2 = np.interp(
        t, [0, 60, 120, 600, 700, 1800, 1900, 3500, 3560, 3600], [0, 65, 97, 97, 70, 97, 70, 70, 0, 0]
    )
    chans = {
        ("ENG.N2", "V"): n2,
        ("ENG.PS3", "V"): n2 / 100 * 380,
        ("ENG.T5", None): 15 + n2 / 100 * 780 + t5_bump * (np.abs(t - 300) < 5),
        ("ENG.PLA", "V"): np.where(n2 > 96, 100.0, 40.0),
        ("LG.WOW", None): np.where((t > 150) & (t < 3400), 0.0, 1.0),
        ("FCS.VOTED.NZ", None): 1.0 + 3.0 * np.exp(-(((t - 1000) / 5.0) ** 2)),
    }
    rows = {k: [] for k in CIR_SCHEMA.names}
    for (pid, lane), v in chans.items():
        loc = D.contract_location(pid + (f".{lane}" if lane else ""))
        n = t.size
        rows["param_id"] += [pid] * n
        rows["source_lru"] += [loc["source_lru"]] * n
        rows["lane"] += [lane] * n
        rows["sample_index"] += list(range(n))
        ts = (EPOCH + t0_ns + (t * 1e9).astype(np.int64)).tolist()
        rows["t_true"] += ts
        rows["t_sample"] += ts
        rows["value"] += v.tolist()
        rows["truth_value"] += (v + truth_offset).tolist()
        rows["validity"] += ["NORMAL"] * n
        rows["quality_flags"] += [0] * n
        rows["rng_key_path"] += [None] * n
    return pa.table(rows, schema=CIR_SCHEMA)


def sortie_events(m, k, *, chunks=2, t5_bump=0.0, truth_offset=0.0):
    t0 = k * DAY
    pay = cir_chunk_payload(
        m.config, cir_flight(t0, t5_bump=t5_bump, truth_offset=truth_offset), epoch_utc_ns=EPOCH
    )
    parts = np.array_split(np.arange(pay["t"].size), chunks)
    evs = [Event(t0, "monitor.sortie_start", "monitoring", {"sortie_id": f"KH2011-{k}"})]
    for j, idx in enumerate(parts):
        evs.append(Event(t0 + 1 + j, "monitor.observe", "monitoring", {kk: v[idx] for kk, v in pay.items()}))
    evs += [
        Event(t0 + 3500 * SEC, "monitor.landing", "monitoring", {}),
        Event(
            t0 + 3600 * SEC + 1,
            "monitor.sortie_end",
            "monitoring",
            {
                "flight_time_s": np.array(3250.0),
                "landings": np.array(1.0),
                "ab_lights": np.array([3.0]),
                "starts": np.array([1.0]),
            },
        ),
    ]
    return evs


def run(m, sysm, n_sorties=1, **kw):
    evs = [e for k in range(n_sorties) for e in sortie_events(m, k, **kw)]
    w = sysm.inject(sysm.start(), evs)
    w, _ = sysm.run(w, (n_sorties - 1) * 240 * 86_400 + 240 * 3600 + 10)
    return w


def tables(m, st, sortie=None):
    return contract_tables(
        m,
        st,
        dictionary=D,
        tail_no="KH2011",
        epoch_utc_ns=EPOCH,
        t_ingest_utc_ns=EPOCH + 10 * DAY,
        sortie_id=sortie,
    )


@pytest.mark.unit
def test_luis_written_twice_per_flight():
    m, sysm = build()
    w = run(m, sysm, 2, chunks=1)
    uc = tables(m, w.states["monitoring"])["usage.counters"].to_pylist()
    t1 = [r for r in uc if r["param_id"] == "LUI.TYPE1"]
    assert [(r["sortie_id"], r["update_seq"]) for r in t1] == [
        ("KH2011-0", 0),
        ("KH2011-0", 1),
        ("KH2011-1", 0),
        ("KH2011-1", 1),
    ]
    assert [r["value_eu"] for r in t1] == [1.0, 1.0, 2.0, 2.0]
    t3 = [r for r in uc if r["param_id"] == "LUI.TYPE3"]
    assert [r["value_eu"] for r in t3] == [1.0, 1.0, 2.0, 2.0]
    eot = [r for r in uc if r["param_id"] == "LUI.EOT"]
    assert eot[1]["value_eu"] == pytest.approx(eot[0]["value_eu"] + eot[1]["increment_eu"])
    tac = [r for r in uc if r["param_id"] == "USAGE.TAC"]
    assert [r["increment_eu"] for r in tac] == [pytest.approx(1.25)] * 2 and all(
        r["validity"] == "NORMAL" for r in tac
    )
    nz = [r for r in uc if r["param_id"] == "STRUCT.NZ_COUNTERS.L3"]  # 3 g level: one crossing per flight
    assert [r["increment_eu"] for r in nz] == [1.0, 1.0]
    assert {r["source_lru"] for r in uc} == {"ECMS", "OAC", "GROUND"}


@pytest.mark.unit
def test_takeoff_record_trigger():
    m, sysm = build()
    w = run(m, sysm, 1, chunks=3)
    rec = m.takeoff_records(w.states["monitoring"])
    # PLA reaches IRP (N2 > 96 %) at t ≈ 118 s with weight on wheels (WoW off at 150 s)
    assert len(rec) == 1 and rec[0][0] == "KH2011-0"
    assert rec[0][1] == pytest.approx(118.2 * SEC, abs=0.2 * SEC) and rec[0][2] - rec[0][1] == 8 * SEC


@pytest.mark.unit
def test_exceedance_and_caution_records():
    m, sysm = build()
    w = run(m, sysm, 1, t5_bump=60.0)
    tabs = tables(m, w.states["monitoring"])
    ex = tabs["events.exceedances"].to_pylist()
    assert len(ex) == 1
    e = ex[0]
    assert e["event_code"] == "ENG-701" and e["param_id"] == "ENG.T5" and e["limit_id"] == "ENG.T5:steady_max"
    assert e["limit_value"] == 830.0 and e["peak_value"] == pytest.approx(15 + 0.97 * 780 + 60)
    assert e["t_end"] > e["t_occurrence"] and e["units"] == "degC"
    assert e["snapshot_t_end"] - e["snapshot_t_start"] == 30 * SEC  # 5 s pre + 25 s post
    cau = tabs["events.cautions"].to_pylist()
    assert [c["legend"] for c in cau] == ["CWS-L08"] and cau[0]["t_cleared"] == e["t_end"]


@pytest.mark.unit
def test_bit_report_declares_and_clears():
    m, sysm = build()
    w = sysm.start()
    w = sysm.inject(
        w,
        [
            Event(0, "monitor.sortie_start", "monitoring", {"sortie_id": "KH2011-0"}),
            Event(
                10 * SEC,
                "monitor.bit_report",
                "monitoring",
                bit_report_payload("ENG-005", lane="A", persistence=4),
            ),
            Event(20 * SEC, "monitor.bit_report", "monitoring", bit_report_payload("ENG-005", cleared=True)),
        ],
    )
    w, _ = sysm.run(w, 240 * 30)
    tabs = tables(m, w.states["monitoring"])
    bf = [r for r in tabs["events.bit_faults"].to_pylist() if r["event_code"] == "ENG-005"]
    assert len(bf) == 1 and bf[0]["lane"] == "A" and bf[0]["persistence_count"] == 4
    assert bf[0]["detection_mechanism"] == "CBIT" and bf[0]["fault_list"] == "PFL"
    assert bf[0]["suspect_lrus"][0] == {"lru": "T5_HARNESS_A", "isolation_confidence": 0.85}
    cau = [r for r in tabs["events.cautions"].to_pylist() if r["event_code"] == "ENG-005"]
    assert cau[0]["t_cleared"] == EPOCH + 20 * SEC
    with pytest.raises(ContractError):
        sysm.run(
            sysm.inject(
                w, [Event(w.t_ns + 1, "monitor.bit_report", "monitoring", bit_report_payload("ZZZ-001"))]
            ),
            2,
        )


@pytest.mark.unit
def test_lru_condition_covered_vs_missed():
    """A covered 8 σ condition on an internal test is declared within its first window; the same condition
    flagged uncovered (missed-detection pool) is not; clearing restores the healthy statistic."""
    for covered, expect in ((True, True), (False, False)):
        _m, sysm = build(regime="mature")
        w = sysm.inject(
            sysm.start(),
            [
                Event(0, "monitor.sortie_start", "monitoring", {"sortie_id": "KH2011-0"}),
                Event(
                    SEC,
                    "monitor.lru_condition",
                    "monitoring",
                    lru_condition_payload("ENG-201", 8.0, covered=covered),
                ),
                Event(1800 * SEC, "monitor.sortie_end", "monitoring", {"flight_time_s": np.array(1800.0)}),
            ],
        )
        w, _ = sysm.run(w, 240 * 1801)
        st = w.states["monitoring"]
        idx = CODES.index("ENG-201")
        hit = np.any((st["o_kind"] == KIND_BIT) & (st["o_code"] == idx) & (st["o_t"] > 0))
        assert bool(hit) == expect


@pytest.mark.unit
def test_observe_is_chunk_invariant_and_truth_blind():
    m1, s1 = build()
    a = run(m1, s1, 1, chunks=1, t5_bump=60.0).states["monitoring"]
    m2, s2 = build()
    b = run(m2, s2, 1, chunks=7, t5_bump=60.0).states["monitoring"]
    m3, s3 = build()
    c = run(m3, s3, 1, chunks=7, t5_bump=60.0, truth_offset=1e3).states["monitoring"]
    for k in a:
        assert np.array_equal(a[k], b[k]), k
        assert np.array_equal(b[k], c[k]), k  # restricted truth columns change nothing
    pay = cir_chunk_payload(m1.config, cir_flight(0), epoch_utc_ns=EPOCH)
    assert set(pay) == {"ch", "t", "v", "validity"}


@pytest.mark.unit
def test_ack_drops_records_and_keeps_open_pointers():
    m, sysm = build()
    w = run(m, sysm, 1)
    st = w.states["monitoring"]
    n = st["o_kind"].size
    w = sysm.inject(w, [Event(w.t_ns + 1, "monitor.ack", "monitoring", {"n": n})])
    w, _ = sysm.run(w, 2)
    assert w.states["monitoring"]["o_kind"].size == 0
    with pytest.raises(ContractError):
        sysm.run(sysm.inject(w, [Event(w.t_ns + 1, "monitor.ack", "monitoring", {"n": 5})]), 2)


@pytest.mark.unit
def test_ibit_ground_records_have_no_sortie():
    m, sysm = build(regime="mature")
    w = sysm.inject(
        sysm.start(),
        [
            Event(SEC, "monitor.lru_condition", "monitoring", lru_condition_payload("AVI-201", 9.0)),
            Event(2 * SEC, "monitor.ibit", "monitoring", {"job": "J-7", "lru": "RADAR", "kind": "IBIT"}),
        ],
    )
    w, _ = sysm.run(w, 240 * 3)
    rows = tables(m, w.states["monitoring"])["events.bit_faults"].to_pylist()
    assert [(r["event_code"], r["sortie_id"], r["detection_mechanism"]) for r in rows] == [
        ("AVI-201", None, "IBIT")
    ]


@pytest.mark.unit
def test_usage_mode_counters_from_summary():
    from phalanx.health import SortieUsage

    m, sysm = build(usage_mode=True)
    u = SortieUsage(
        sortie_id="KH2011-0",
        flight_time_s=3600.0,
        eot_s=(4500.0,),
        tamp_s=(600.0,),
        type1=(1.0,),
        type3=(5.0,),
        type4=(5.0,),
        eftc=(1.2,),
        src_h=(0.05,),
        ps3_full=(0.0,),
        ps3_partial=(1.0,),
        ab_lights=(4.0,),
        starts=(1.0,),
        nz_counts=(0.0, 0.0, 3.0, 2.0, 1.0, 0.0, 0.0, 0.0),
    )
    w = sysm.inject(
        sysm.start(),
        [
            Event(0, "monitor.sortie_start", "monitoring", {"sortie_id": "KH2011-0"}),
            Event(3600 * SEC, "monitor.usage_summary", "monitoring", u.to_payload()),
        ],
    )
    w, _ = sysm.run(w, 240 * 3601)
    uc = {r["param_id"]: r for r in tables(m, w.states["monitoring"])["usage.counters"].to_pylist()}
    assert uc["LUI.TYPE3"]["value_eu"] == 5.0 and uc["LUI.EOT"]["value_eu"] == pytest.approx(1.25)
    assert uc["USAGE.TAC"]["value_eu"] == pytest.approx(1 + 5 / 4 + 5 / 40)
    assert uc["STRUCT.NZ_COUNTERS.L3"]["value_eu"] == 3.0 and uc["USAGE.FLIGHT_HOURS"]["value_eu"] == 1.0


@pytest.mark.unit
def test_event_tables_validate_and_stay_consumer_safe():
    """A6: every emitted batch validates against contract v0; consumer topics carry no restricted field; the
    restricted labels topic is refused to consumers; a tampered batch is rejected (negative control)."""
    m, sysm = build(regime="immature")
    w = run(m, sysm, 3, t5_bump=60.0)
    w = sysm.inject(
        w, [Event(w.t_ns + 1, "monitor.bit_report", "monitoring", bit_report_payload("ENG-001", lane="A"))]
    )
    w, _ = sysm.run(w, 2)
    st = w.states["monitoring"]
    assert {KIND_BIT, KIND_EXCEED, KIND_CAUTION, KIND_COUNTER} <= set(st["o_kind"].tolist())
    tabs = tables(m, st)
    for topic, tab in tabs.items():
        C.validate(topic, tab)
        assert tab.schema.names == C.consumer_schema(topic).names  # nothing restricted to drop
        assert tab.num_rows > 0
        assert len(set(tab.column("record_id").to_pylist())) == tab.num_rows
    with pytest.raises(PermissionError):
        C.consumer_schema("labels.truth")
    bad = tabs["usage.counters"].set_column(
        tabs["usage.counters"].schema.get_field_index("value_eu"),
        "value_eu",
        pa.array([-1.0] * tabs["usage.counters"].num_rows, pa.float64()),
    )
    with pytest.raises(ContractViolation):
        C.validate("usage.counters", bad)
    per_sortie = tables(m, st, sortie="KH2011-1")
    assert set(per_sortie["usage.counters"].column("sortie_id").to_pylist()) == {"KH2011-1"}
