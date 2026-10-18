"""W0.4 A6 (property): ``as_of(t)`` never returns a record with t_ingest > t, and returns every record first
ingested at or before t exactly once (information discipline, invariant I5).

Each example builds a small store: 1-4 sorties, each with an initial download and 0-2 re-downloads (full or
partial) at random later times; then checks as_of, the replay cut-off ``until`` and ``ingested`` at random t.
n per example: up to 4 sorties x 3 streams x 6 samples = 72 records; 40 examples. Small on purpose: the
property is about ordering logic, which every example exercises; larger stores add runtime, not coverage.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pyarrow as pa
import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from phalanx.dictionary.contract import load_contract
from phalanx.ground import FastPathConfig, cir_to_param_samples
from phalanx.ground.examples import example_cir_batch, example_units
from phalanx.streaming import ObservationView, ParquetStore, ReplayBatch, ReplayStreamer

C = load_contract("v0")
E = 1_791_000_000 * 10**9
S = 10**9
CFG = FastPathConfig("0.1.0", "ab" * 32, example_units())

_download = st.tuples(st.integers(0, 50), st.integers(1, 6))  # (ingest offset in s after the data, n samples)
_sortie = st.tuples(st.integers(1, 6), st.lists(_download, min_size=0, max_size=2))  # first n, re-downloads


@pytest.mark.property
@settings(max_examples=40, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(st.lists(_sortie, min_size=1, max_size=4), st.lists(st.integers(-5, 120), min_size=1, max_size=5))
def test_a6_as_of_never_returns_future_records(sorties, probes):
    first_ingest: dict[bytes, int] = {}
    with tempfile.TemporaryDirectory() as d:
        store = ParquetStore(Path(d), C)
        for k, (n0, redownloads) in enumerate(sorties):
            sortie = f"S{k}"
            data_end = E + 6 * S  # every example stream ends within 6 s of E
            for offset, n in [(k * 7, n0), *redownloads]:
                ingest = data_end + offset * S
                t = cir_to_param_samples(example_cir_batch("T1", sortie, E, n), CFG, t_ingest=ingest)
                store.write("param.samples", t, date="2026-10-03")
                for rid in t.column("record_id").to_pylist():
                    first_ingest[rid] = min(first_ingest.get(rid, ingest), ingest)
        view = ObservationView(store)
        for p in probes:
            t_now = E + 6 * S + p * S
            got = view.as_of(t_now, "param.samples")
            ingests = got.column("t_ingest").to_pylist()
            assert all(v <= t_now for v in ingests)  # A6: never a future record
            ids = got.column("record_id").to_pylist()
            assert len(ids) == len(set(ids))  # idempotent: each record once
            expected = {r for r, ti in first_ingest.items() if ti <= t_now}
            assert set(ids) == expected  # complete: nothing ingested is withheld
            assert all(
                first_ingest[r] == ti for r, ti in zip(ids, ingests, strict=True)
            )  # earliest copy kept
            # the streaming cut-off obeys the same discipline
            for item in ReplayStreamer(store, ["param.samples"], until=t_now):
                if isinstance(item, ReplayBatch):
                    assert item.t_ingest <= t_now
            # the evidence check used by orders agrees with as_of
            probe_ids = list(first_ingest)
            flags = view.ingested(t_now, probe_ids)
            assert [bool(f) for f in flags] == [first_ingest[r] <= t_now for r in probe_ids]


@pytest.mark.property
def test_a6_restricted_and_unobservable_topics_refused(tmp_path):
    from phalanx.dictionary.contract.examples import example_records

    store = ParquetStore.at(tmp_path, C)
    store.write("labels.truth", example_records(C, "labels.truth", 2))
    view = ObservationView(store)
    with pytest.raises(PermissionError):
        view.as_of(E, "labels.truth")
    # the validation audience may read labels via the store, but labels have no ingest time: not "observable"
    with pytest.raises(PermissionError):
        ObservationView(store, audience="validation").as_of(E, "labels.truth")
    with pytest.raises(PermissionError):  # least privilege: the default read audience is consumer
        store.read("labels.truth")
    assert store.read("labels.truth", audience="validation").num_rows == 2
    # a consumer-only store (no restricted root) cannot reach restricted data at all
    consumer_only = ParquetStore(store.root, C)
    with pytest.raises(PermissionError):
        consumer_only.read("labels.truth", audience="validation")
    assert isinstance(ObservationView(consumer_only).as_of(E, "param.samples"), pa.Table)
