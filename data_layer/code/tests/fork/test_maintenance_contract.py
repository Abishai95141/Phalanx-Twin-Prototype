"""A6 contract conformance and A1 key integrity at fleet scale; the defect manifest stays restricted.

One closed-loop run: 6 tails x 60 days, condition-based policy, a modification and a software-load order,
data-quality defects on, a ParquetStore with separate consumer/restricted trees (n = 1 run; every record of
the run is checked, about 3,000 maint.records rows).
"""

from __future__ import annotations

import itertools
from collections import defaultdict

import pytest
from test_fork_fixture_fleet import DAY, EPOCH, FixtureFleetBuilder

from phalanx.dictionary.contract import load_contract
from phalanx.fork.service import BranchSpec, ForkService
from phalanx.fork.session import OpsSession
from phalanx.maintenance.defects import DefectInjector
from phalanx.maintenance.records import LABELS, MAINT, ORDERS_COMMANDS, ORDERS_STATUS, rid_hex, rows_to_table
from phalanx.orders.model import Order
from phalanx.orders.policies import ConditionBasedPolicy
from phalanx.streaming.leak_audit import audit_consumer_tree
from phalanx.streaming.memory_view import MemoryObservations
from phalanx.streaming.parquet_store import ParquetStore

ROOT = 0xA6A6
C = load_contract("v0")
SECTION_10 = {
    "SORTIE",
    "TECH_LOG",
    "DEFECT_WO",
    "COMPONENT_LIFE",
    "INSPECTION",
    "SUPPLY_DEMAND",
    "CANNIBALISATION",
    "MODIFICATION",
    "EXCEEDANCE_INSPECTION",
    "SHOP_FINDING",
    "AVAILABILITY_STATE",
}


@pytest.fixture(scope="module")
def run(tmp_path_factory):
    b = FixtureFleetBuilder(n_tails=6, horizon_days=60)
    store = ParquetStore.at(tmp_path_factory.mktemp("w18_store"), C)

    def defects(root):
        return DefectInjector(
            b.m18_cfg.defects,
            root=root,
            scenario=b.scenario,
            contract=C,
            dict_version=b.dict_version,
            dict_hash=b.dict_hash,
        )

    s = OpsSession(b, ROOT, defects=defects(ROOT), store=store)
    t = b.calendar.next_epoch(5 * DAY)
    s.run_until(t)
    s.submit(
        [
            Order(
                "MOD-1",
                "AIRHQ",
                "HUMAN",
                EPOCH + t,
                EPOCH + t,
                "EMBODY_MODIFICATION",
                {"mod_id": "MOD-FQGS-PICKUP"},
                target_base="SUL",
            ),
            Order(
                "SW-1",
                "AIRHQ",
                "HUMAN",
                EPOCH + t,
                EPOCH + t,
                "LOAD_SOFTWARE",
                {"sw_config_id": "SW-BRK-Y"},
                target_tail_no=b.tails[0],
            ),
        ]
    )
    fs = ForkService(b, b.m18_cfg, defects_factory=defects)
    res = fs.run(s.snapshot(), BranchSpec("cbm", policy=ConditionBasedPolicy()), 55 * DAY, keep_session=True)
    return b, res.session, store, s


@pytest.mark.fork
def test_every_batch_conforms_and_record_ids_are_unique_over_the_run(run):
    _, s, _, _ = run
    for topic in (MAINT, ORDERS_COMMANDS, ORDERS_STATUS, LABELS, "events.bit_faults"):
        rows = s.records(topic)
        assert rows, topic
        rows_to_table(C, topic, rows)  # validates the whole run as one batch (incl. unique record_id)
    types = {r["record_type"] for r in s.records(MAINT)}
    assert types == SECTION_10


@pytest.mark.fork
def test_key_integrity_of_maintenance_records(run):
    b, s, _, _ = run
    rows = s.records(MAINT)
    by_key = defaultdict(list)
    for r in rows:
        assert r["record_id"] == rid_hex(
            C,
            MAINT,
            {
                "record_type": r["record_type"],
                "record_key": r["record_key"],
                "record_version": r["record_version"],
            },
        )
        by_key[(r["record_type"], r["record_key"])].append(r)
        assert r["tail_no"] is None or r["tail_no"] in b.tails
        assert r["t_ingest"] >= r["t_event"]
    keys = {k for _, k in by_key}
    for (rt, key), vers in by_key.items():
        assert [v["record_version"] for v in vers] == list(range(len(vers))), (rt, key)
        closed = [i for i, v in enumerate(vers) if v["status"] == "CLOSED"]
        assert closed in ([], [len(vers) - 1]), (rt, key)  # nothing after a close
    for r in rows:
        for f in ("job_no", "linked_job_no"):
            if r[f] is not None and r["record_type"] != "COMPONENT_LIFE":
                assert r[f] in keys or r[f].endswith("-CN"), (f, r[f])
        if r["record_type"] == "SUPPLY_DEMAND" and r["job_no"] is not None:
            assert r["job_no"] in keys
    # component life alternates INSTALL / REMOVE per serial; a shop finding follows a removal
    moves = defaultdict(list)
    for r in rows:
        if r["record_type"] == "COMPONENT_LIFE":
            moves[r["serial_no"]].append((r["record_version"], r["install_action"], r["t_event"]))
    for sn, mv in moves.items():
        acts = [a for _, a, _ in sorted(mv)]
        assert all(x != y for x, y in itertools.pairwise(acts)), sn
    for r in rows:
        if r["record_type"] == "SHOP_FINDING":
            assert any(a == "REMOVE" and t <= r["t_event"] for _, a, t in moves[r["serial_no"]])


@pytest.mark.fork
def test_order_lifecycle_records(run):
    _, s, _, _ = run
    st = defaultdict(list)
    for r in s.records(ORDERS_STATUS):
        st[r["order_id"]].append(r)
    cmds = [r["order_id"] for r in s.records(ORDERS_COMMANDS)]
    assert len(cmds) == len(set(cmds)) == len(st) >= 3
    maint_ids = {r["record_id"] for r in s.records(MAINT)}
    for _oid, recs in st.items():
        assert [r["status_seq"] for r in recs] == list(range(len(recs)))
        assert recs[0]["status"] in ("ACCEPTED", "REJECTED")
        terminal = [r for r in recs if r["status"] in ("COMPLETED", "REJECTED")]
        assert len(terminal) <= 1 and (not terminal or terminal[0] is recs[-1])
        for r in recs:
            assert set(r["result_record_ids"]) <= maint_ids
    done = [recs[-1] for recs in st.values() if recs[-1]["status"] == "COMPLETED"]
    assert any(r["result_record_ids"] for r in done), "executed orders produce normal records"


@pytest.mark.fork
def test_defect_manifest_is_restricted_and_consistent(run):
    _, s, store, parent = run
    labels = s.records(LABELS)
    kinds = {r["subject_id"] for r in labels}
    assert {"DQ.TEXT_NOISE", "DQ.RECON_LAG"} <= kinds and all(r["label_kind"] == "DEFECT" for r in labels)
    truth_ids = {r["record_id"] for r in s.records(MAINT)}
    observed = s.obs.as_of(EPOCH + 10_000 * DAY, MAINT)
    obs_ids = {bytes(x).hex() for x in observed.column("record_id").to_pylist()}
    for r in labels:
        if r["subject_id"] in ("DQ.MISSING_PART_RECORD", "DQ.CANN_UNDERREPORT"):
            assert r["related_record_id"] in truth_ids and r["related_record_id"] not in obs_ids
        if r["subject_id"] in ("DQ.DUPLICATE_SNAG", "DQ.WRONG_FORM"):
            assert r["related_record_id"] in obs_ids and r["related_record_id"] not in truth_ids
    # physically separate: the consumer tree has no labels and passes the leak audit (seed and label values)
    assert store.files(LABELS, tree="restricted") and not (store.root / LABELS).exists()
    assert audit_consumer_tree(store.root, C, secrets=[f"{ROOT:032x}"]) == []
    with pytest.raises(PermissionError):
        MemoryObservations(C).append(LABELS, rows_to_table(C, LABELS, labels[:3]))
    with pytest.raises(PermissionError):
        s.obs.as_of(EPOCH, LABELS)
    assert parent.store is store  # the parent wrote the pre-fork records to the same trees
