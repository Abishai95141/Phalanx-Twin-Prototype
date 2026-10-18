"""A4 no look-ahead (property): an order citing any record not ingested by t_issued is rejected; otherwise the
evidence check passes. Also the indexed evidence lookup and the in-memory observation set agree exactly with
the W0.4 ``ObservationView`` on the same stored records (I5 semantics preserved).

Sample: hypothesis, 60 examples per property (each a fresh set of 1-12 records over a 10-day window).
"""

from __future__ import annotations

import tempfile

import numpy as np
import pyarrow as pa
import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from phalanx.maintenance.records import MAINT, contract_v0, maint_row, rows_to_table
from phalanx.orders.epochs import DecisionCalendar
from phalanx.orders.gateway import OrderGateway
from phalanx.orders.model import Order
from phalanx.orders.rules import load_authority
from phalanx.streaming.ingest_index import IndexedObservationView
from phalanx.streaming.memory_view import MemoryObservations
from phalanx.streaming.parquet_store import ParquetStore
from phalanx.streaming.replay import ObservationView

NS = 1_000_000_000
H = 3600 * NS
EPOCH = 1_790_035_200 * NS
C = contract_v0()


def _rows(spec):
    out = []
    for i, (tail, ev_h, lag_h) in enumerate(spec):
        t_event = EPOCH + ev_h * H
        out.append(
            maint_row(
                C,
                dict_version="0.1.1",
                dict_hash="ab" * 16,
                record_type="TECH_LOG",
                record_key=f"TL-{tail}",
                record_version=i,
                t_event=t_event,
                t_ingest=t_event + lag_h * H,
                tail_no=tail,
                availability_state="FMC",
            )
        )
    return out


records = st.lists(
    st.tuples(st.sampled_from(["T01", "T02"]), st.integers(0, 200), st.integers(0, 40)),
    min_size=1,
    max_size=12,
)


@pytest.mark.property
@settings(max_examples=60, deadline=None)
@given(spec=records, t_issue_h=st.integers(0, 260), pick=st.lists(st.integers(0, 11), min_size=1, max_size=4))
def test_order_citing_uningested_evidence_is_rejected(spec, t_issue_h, pick):
    rows = _rows(spec)
    obs = MemoryObservations(C)
    obs.append(MAINT, rows_to_table(C, MAINT, rows))
    cited = [rows[i % len(rows)] for i in pick]
    t_issued = EPOCH + t_issue_h * H
    gw = OrderGateway(
        contract=C,
        calendar=DecisionCalendar(EPOCH, 19_800, (28_800,)),
        authority=load_authority(),
        epoch_utc_ns=EPOCH,
    )
    order = Order(
        "LA-1",
        "AGENT-1",
        "AGENT",
        t_issued,
        t_issued,
        "INSPECT",
        {"type": "NDT"},
        target_tail_no="T01",
        evidence=tuple(bytes.fromhex(r["record_id"]) for r in cited),
    )
    verdict, reason, _ = gw.evaluate(order, t_issue_h * H, obs)
    future = any(r["t_ingest"] > t_issued for r in cited)
    assert (verdict == "REJECTED") == future
    if future:
        assert "not ingested" in reason
    # an id that was never recorded is never "ingested"
    ghost = Order(
        "LA-2",
        "AGENT-1",
        "AGENT",
        t_issued,
        t_issued,
        "INSPECT",
        {"type": "NDT"},
        target_tail_no="T01",
        evidence=(b"\x07" * 16,),
    )
    assert gw.evaluate(ghost, t_issue_h * H, obs)[0] == "REJECTED"


@pytest.mark.property
@settings(max_examples=40, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(
    batches=st.lists(records, min_size=1, max_size=3),
    times=st.lists(st.integers(0, 260), min_size=1, max_size=4),
)
def test_index_and_memory_view_match_observation_view(batches, times):
    with tempfile.TemporaryDirectory() as d:
        store = ParquetStore.at(d, C)
        mem = MemoryObservations(C)
        allrows = []
        for b, spec in enumerate(batches):
            rows = _rows(spec)
            for r in rows:  # distinct record keys per batch (versions restart per batch)
                r["record_key"] = f"{r['record_key']}-{b}"
                r["record_id"] = maint_row(
                    C,
                    dict_version="0.1.1",
                    dict_hash="ab" * 16,
                    record_type="TECH_LOG",
                    record_key=r["record_key"],
                    record_version=r["record_version"],
                    t_event=r["t_event"],
                    t_ingest=r["t_ingest"],
                )["record_id"]
            tab = rows_to_table(C, MAINT, rows)
            store.write(MAINT, tab)
            mem.append(MAINT, tab)
            allrows += rows
        ov, iv = ObservationView(store), IndexedObservationView(store)
        ids = [bytes.fromhex(r["record_id"]) for r in allrows] + [b"\x01" * 16]
        for th in times:
            t = EPOCH + th * H
            a, b2, c = ov.ingested(t, ids), iv.ingested(t, ids), mem.ingested(t, ids)
            assert np.array_equal(a, b2) and np.array_equal(a, c)
            for tail in (None, "T01"):
                x = ov.as_of(t, MAINT, tail_no=tail)
                y = mem.as_of(t, MAINT, tail_no=tail)
                assert x.equals(y.cast(x.schema)), (th, tail)
                assert all(v <= t for v in pa.array(y.column("t_ingest")).to_pylist())
