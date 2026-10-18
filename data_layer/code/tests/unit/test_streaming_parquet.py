"""W0.4 A3: Arrow <-> Parquet <-> Arrow is lossless and Parquet bytes are identical across writes.

Plus the store's partition layout, reads by sortie / tail / date / time window, idempotent writes and contract
checks on read. Samples: EXAMPLE records (4 per topic) and an EXAMPLE CIR batch (3 streams x 10 = 30 samples).
"""

from __future__ import annotations

import hashlib
import re
import subprocess
import sys

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from phalanx.dictionary.contract import load_contract, load_spec_dir
from phalanx.dictionary.contract.examples import example_records
from phalanx.dictionary.contract.loader import SPEC_ROOT
from phalanx.ground import FastPathConfig, cir_to_param_samples
from phalanx.ground.examples import example_cir_batch, example_units
from phalanx.streaming import (
    CONSUMER,
    RESTRICTED,
    ParquetStore,
    StoreError,
    parquet_bytes,
    project_consumer,
    utc_date,
)

C = load_contract("v0")
EPOCH = 1_791_000_000 * 10**9
CFG = FastPathConfig("0.1.0", "ab" * 32, example_units())


def _samples(tail="T001", sortie="T001-S1", n=10, ingest_h=4, first=0) -> pa.Table:
    b = example_cir_batch(tail, sortie, EPOCH, n, first_index=first)
    return cir_to_param_samples(b, CFG, t_ingest=EPOCH + ingest_h * 3600 * 10**9)


@pytest.mark.unit
@pytest.mark.parametrize("topic", C.topic_names)
def test_a3_roundtrip_lossless_every_topic(tmp_path, topic):
    """Full records -> consumer tree + restricted tree -> validation read (joined by record_id) == input;
    consumer read == the consumer projection of the input; every file carries its tree's exact schema."""
    t = example_records(C, topic, 4)
    store = ParquetStore.at(tmp_path, C)
    store.write(topic, t)
    key = [(C.topics[topic].event_time, "ascending"), ("record_id", "ascending")]
    full = store.read(topic, audience="validation", dedup=False)
    assert full.equals(t.sort_by(key).combine_chunks(), check_metadata=True)
    C.validate(topic, full)
    if C.topics[topic].restricted:
        assert store.files(topic, tree=CONSUMER) == []
        with pytest.raises(PermissionError):
            store.read(topic)
    else:
        consumer = store.read(topic, dedup=False)  # default audience: consumer
        expected = project_consumer(C, topic, t).sort_by(key).combine_chunks()
        assert consumer.equals(expected, check_metadata=True)
    for tree in (CONSUMER, RESTRICTED):
        for f in store.files(topic, tree=tree):
            assert pq.read_schema(f).equals(store.tree_schema(topic, tree), check_metadata=True)


@pytest.mark.unit
@pytest.mark.determinism
def test_a3_parquet_bytes_identical_across_writes(tmp_path, repo_root):
    t = _samples()
    b1, b2 = parquet_bytes(t), parquet_bytes(t)
    assert b1 == b2
    p1 = ParquetStore(tmp_path / "a", C).write("param.samples", t, date="2026-10-03")
    p2 = ParquetStore(tmp_path / "b", C).write("param.samples", t, date="2026-10-03")
    assert [p.relative_to(tmp_path / "a") for p in p1] == [p.relative_to(tmp_path / "b") for p in p2]
    assert [p.read_bytes() for p in p1] == [p.read_bytes() for p in p2]
    # a fresh interpreter writes the same bytes (no process-dependent state)
    code = (
        "import sys, hashlib; sys.path.insert(0, sys.argv[1]);"
        "from phalanx.ground import FastPathConfig, cir_to_param_samples;"
        "from phalanx.ground.examples import example_cir_batch, example_units;"
        "from phalanx.streaming import parquet_bytes, canonical_order, project_consumer;"
        "from phalanx.dictionary.contract import load_contract; c = load_contract('v0');"
        "E = 1_791_000_000 * 10**9;"
        "t = cir_to_param_samples(example_cir_batch('T001', 'T001-S1', E, 10),"
        " FastPathConfig('0.1.0', 'ab' * 32, example_units()), t_ingest=E + 4 * 3600 * 10**9);"
        "t = project_consumer(c, 'param.samples', t);"
        "print(hashlib.blake2b(parquet_bytes(canonical_order(c, 'param.samples', t))).hexdigest())"
    )
    out = subprocess.run(
        [sys.executable, "-I", "-c", code, str(repo_root / "src")], capture_output=True, text=True, check=True
    ).stdout.strip()
    assert out == hashlib.blake2b(p1[0].read_bytes()).hexdigest()


@pytest.mark.unit
def test_a3_bytes_independent_of_input_row_order(tmp_path):
    t = _samples()
    rev = t.take(pa.array(list(reversed(range(t.num_rows)))))
    a = ParquetStore(tmp_path / "a", C).write("param.samples", t, date="2026-10-03")
    b = ParquetStore(tmp_path / "b", C).write("param.samples", rev, date="2026-10-03")
    assert a[0].read_bytes() == b[0].read_bytes()


@pytest.mark.unit
def test_a3_no_wall_clock_or_host_metadata(tmp_path):
    p = ParquetStore(tmp_path, C).write("param.samples", _samples(), date="2026-10-03")[0]
    md = pq.read_metadata(p)
    assert md.created_by == f"parquet-cpp-arrow version {pa.__version__}"  # pinned writer version only
    # file key-values = the stored Arrow schema + the contract's schema metadata; nothing host- or
    # time-specific
    expected = dict(C.consumer_schema("param.samples").metadata)
    kv = dict(md.metadata)
    assert kv.pop(b"ARROW:schema")
    assert kv == expected
    assert md.num_row_groups == 1


@pytest.mark.unit
def test_store_write_is_idempotent_and_redownload_is_a_new_file(tmp_path):
    store = ParquetStore(tmp_path, C)
    t = _samples()
    p1 = store.write("param.samples", t, date="2026-10-03")
    p2 = store.write("param.samples", t, date="2026-10-03")
    assert p1 == p2 and len(store.files("param.samples")) == 1
    later = _samples(ingest_h=9)
    p3 = store.write("param.samples", later, date="2026-10-03")
    assert p3 != p1 and len(store.files("param.samples")) == 2
    # the reader deduplicates the re-download, keeping the earliest ingest
    r = store.read("param.samples")
    assert r.num_rows == t.num_rows
    assert set(r.column("t_ingest").to_pylist()) == {EPOCH + 4 * 3600 * 10**9}
    assert store.read("param.samples", dedup=False).num_rows == 2 * t.num_rows


@pytest.mark.unit
def test_store_partition_layout_and_reads(tmp_path):
    store = ParquetStore(tmp_path, C)
    store.write("param.samples", _samples("T001", "T001-S1"), date="2026-10-03")
    store.write("param.samples", _samples("T001", "T001-S2"), date="2026-10-04")
    store.write("param.samples", _samples("T002", "T002-S1"), date="2026-10-04")
    rels = sorted(str(p.relative_to(tmp_path).parent) for p in store.files("param.samples"))
    assert rels == [
        "param.samples/date=2026-10-03/tail_no=T001/sortie_id=T001-S1",
        "param.samples/date=2026-10-04/tail_no=T001/sortie_id=T001-S2",
        "param.samples/date=2026-10-04/tail_no=T002/sortie_id=T002-S1",
    ]
    assert store.read("param.samples", sortie_id="T001-S2").num_rows == 30
    assert set(store.read("param.samples", tail_no="T001").column("sortie_id").to_pylist()) == {
        "T001-S1",
        "T001-S2",
    }
    assert store.read("param.samples", date_from="2026-10-04").num_rows == 60
    assert store.read("param.samples", date_to="2026-10-03").num_rows == 30
    # event-time window [t_from, t_to): EGT is 10 Hz, N2 lanes 50 Hz; first 0.1 s holds 5+5+1 samples per
    # sortie
    w = store.read("param.samples", sortie_id="T001-S1", t_from=EPOCH, t_to=EPOCH + 100_000_000)
    assert w.num_rows == 11
    assert all(EPOCH <= v < EPOCH + 100_000_000 for v in w.column("t_sample").to_pylist())
    # read order is canonical
    ts = store.read("param.samples").column("t_sample").to_pylist()
    assert ts == sorted(ts)


@pytest.mark.unit
def test_store_null_partition_and_derived_date(tmp_path):
    store = ParquetStore(tmp_path, C)
    t = example_records(C, "events.bit_faults", 2)  # row 1 has a null sortie_id
    paths = store.write("events.bit_faults", t)  # date derived from t_occurrence
    rels = sorted(str(p.relative_to(tmp_path).parent) for p in paths)
    assert rels == [
        "events.bit_faults/date=2026-10-03/tail_no=X0/sortie_id=X0",
        "events.bit_faults/date=2026-10-03/tail_no=X1/sortie_id=__null__",
    ]
    assert utc_date(EPOCH) == "2026-10-03" and utc_date(0) == "1970-01-01"


@pytest.mark.unit
def test_store_rejects_foreign_contract_and_bad_input(tmp_path):
    other_dir = tmp_path / "spec"
    import shutil

    shutil.copytree(SPEC_ROOT / "v0", other_dir)
    f = other_dir / "contract.yaml"
    text = f.read_text()
    foreign = re.sub(r"^status: .*$", "status: foreign-test", text, count=1, flags=re.M)
    assert foreign != text  # the edit must really change the spec, whatever the current status is
    f.write_text(foreign)
    other = load_spec_dir(other_dir)
    assert other.hash != C.hash
    store = ParquetStore(tmp_path / "s", C)
    p = store.write("param.samples", _samples(), date="2026-10-03")[0]
    with pytest.raises(StoreError, match="different contract"):
        ParquetStore(tmp_path / "s", other).read_file("param.samples", p)
    with pytest.raises(StoreError, match="YYYY-MM-DD"):
        store.write("param.samples", _samples(), date="03-10-2026")
    with pytest.raises(ValueError, match="partition fields"):
        store.files("param.samples", partitions={"param_id": "x"})
