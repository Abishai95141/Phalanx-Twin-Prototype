"""W0.4 A5: replay in event-time order with per-sortie watermarks; replay output bitwise identical to the
files; duplicates suppressed (idempotent on record_id).

Scenario (EXAMPLE data, 3 streams x 10 samples = 30 records per sortie, the smallest that shows interleaving):
- sortie A of tail T001 downloaded at +4 h, sortie B of tail T002 at +2 h (B arrives first);
- sortie A re-downloaded in full at +6 h (DUPLICATE_DOWNLOAD set; must be suppressed);
- sortie C first downloaded partially at +3 h (first 5 samples per stream), completed at +5 h by a re-download
  of all 10 (the 15 overlapping records are suppressed; the 15 new ones are late relative to the watermark).
"""

from __future__ import annotations

import pyarrow as pa
import pyarrow.compute as pc
import pytest

from phalanx.dictionary.contract import load_contract
from phalanx.dictionary.contract.examples import example_records
from phalanx.ground import FastPathConfig, cir_to_param_samples
from phalanx.ground.examples import example_cir_batch, example_units
from phalanx.streaming import (
    ParquetStore,
    RecordIdConflict,
    ReplayBatch,
    ReplayStreamer,
    Watermark,
)

C = load_contract("v0")
E = 1_791_000_000 * 10**9
H = 3600 * 10**9
CFG = FastPathConfig("0.1.0", "ab" * 32, example_units())
DUP = C.quality_flags.mask("DUPLICATE_DOWNLOAD")


def _samples(tail, sortie, ingest, n=10, epoch=E, dup=False) -> pa.Table:
    t = cir_to_param_samples(example_cir_batch(tail, sortie, epoch, n), CFG, t_ingest=ingest)
    if dup:
        i = t.schema.get_field_index("quality_flags")
        t = t.set_column(i, t.schema.field(i), pc.bit_wise_or(t.column(i), pa.scalar(DUP, pa.uint32())))
    return t


@pytest.fixture
def store(tmp_path) -> ParquetStore:
    s = ParquetStore(tmp_path, C)
    s.write("param.samples", _samples("T001", "A", E + 4 * H), date="2026-10-03")
    s.write("param.samples", _samples("T002", "B", E + 2 * H, epoch=E + 10**9), date="2026-10-03")
    s.write("param.samples", _samples("T001", "A", E + 6 * H, dup=True), date="2026-10-03")
    s.write("param.samples", _samples("T003", "C", E + 3 * H, n=5), date="2026-10-03")
    s.write("param.samples", _samples("T003", "C", E + 5 * H, dup=True), date="2026-10-03")
    return s


def _items(store, **kw):
    return list(ReplayStreamer(store, ["param.samples"], **kw))


@pytest.mark.unit
def test_a5_burst_order_and_event_time_order(store):
    items = _items(store)
    batches = [i for i in items if isinstance(i, ReplayBatch)]
    assert [(b.tail_no, b.sortie_id, b.t_ingest) for b in batches] == [
        ("T002", "B", E + 2 * H),
        ("T003", "C", E + 3 * H),
        ("T001", "A", E + 4 * H),
        ("T003", "C", E + 5 * H),
    ]  # the full duplicate of A at +6 h delivers nothing
    for b in batches:
        ts = b.table.column("t_sample").to_pylist()
        rid = b.table.column("record_id").to_pylist()
        assert all(
            (ts[i], rid[i]) < (ts[i + 1], rid[i + 1]) for i in range(len(ts) - 1)
        )  # strict total order
    assert [b.table.num_rows for b in batches] == [30, 15, 30, 15]


@pytest.mark.unit
def test_a5_per_sortie_watermarks(store):
    items = _items(store)
    marks = [i for i in items if isinstance(i, Watermark)]
    assert [(m.tail_no, m.sortie_id) for m in marks] == [
        ("T002", "B"),
        ("T003", "C"),
        ("T001", "A"),
        ("T003", "C"),
    ]
    # each watermark follows its burst and equals the max event time delivered so far for that sortie
    seen: dict = {}
    for it in items:
        if isinstance(it, ReplayBatch):
            k = (it.tail_no, it.sortie_id)
            seen[k] = max(seen.get(k, 0), pc.max(it.table.column("t_sample")).as_py())
        else:
            assert it.event_time == seen[(it.tail_no, it.sortie_id)]
    c_marks = [m.event_time for m in marks if m.sortie_id == "C"]
    assert c_marks[0] < c_marks[1]  # completing download advances the watermark
    # the completing burst of C: 15 new records, of which those at or before the first watermark are late
    c2 = [b for b in items if isinstance(b, ReplayBatch) and b.sortie_id == "C"][1]
    late = pc.sum(pc.less_equal(c2.table.column("t_sample"), c_marks[0])).as_py()
    assert c2.late_rows == late > 0


@pytest.mark.unit
def test_a5_duplicates_suppressed(store):
    batches = [i for i in _items(store) if isinstance(i, ReplayBatch)]
    ids = [r for b in batches for r in b.table.column("record_id").to_pylist()]
    assert len(ids) == len(set(ids)) == 90  # A 30 + B 30 + C 30, each once
    # survivors are the earliest-ingested copies: nothing from A's +6 h re-download
    a = [b for b in batches if b.sortie_id == "A"]
    assert len(a) == 1 and set(a[0].table.column("t_ingest").to_pylist()) == {E + 4 * H}
    assert not pc.any(pc.not_equal(pc.bit_wise_and(a[0].table.column("quality_flags"), DUP), 0)).as_py()


@pytest.mark.unit
def test_a5_replay_bitwise_identical_to_files(tmp_path):
    s = ParquetStore.at(tmp_path, C)
    files = []
    files += s.write("param.samples", _samples("T001", "A", E + 4 * H), date="2026-10-03")
    files += s.write("param.samples", _samples("T002", "B", E + 2 * H), date="2026-10-03")
    on_disk = {
        s.read_file("param.samples", p).column("sortie_id")[0].as_py(): s.read_file("param.samples", p)
        for p in files
    }
    for audience in ("validation", "consumer"):
        for b in _items(s, audience=audience):
            if not isinstance(b, ReplayBatch):
                continue
            expected = on_disk[b.sortie_id]  # consumer-tree file
            if audience == "validation":  # same bytes of data, full schema (no restricted fields to join)
                schema = C.schemas["param.samples"]
                expected = pa.Table.from_arrays([expected.column(n) for n in schema.names], schema=schema)
            assert b.table.equals(expected, check_metadata=True)
            sink = pa.BufferOutputStream()
            with pa.ipc.new_stream(sink, b.table.schema) as w:
                w.write_table(b.table)
            sink2 = pa.BufferOutputStream()
            with pa.ipc.new_stream(sink2, expected.schema) as w:
                w.write_table(expected.combine_chunks())
            assert sink.getvalue().to_pybytes() == sink2.getvalue().to_pybytes()


@pytest.mark.unit
def test_a5_conflicting_duplicate_raises(tmp_path):
    s = ParquetStore(tmp_path, C)
    t = _samples("T001", "A", E + 4 * H)
    s.write("param.samples", t, date="2026-10-03")
    later = _samples("T001", "A", E + 6 * H)
    i = later.schema.get_field_index("value_eu")
    later = later.set_column(i, later.schema.field(i), pc.add(later.column(i), 1.0))  # same ids, other values
    s.write("param.samples", later, date="2026-10-03")
    with pytest.raises(RecordIdConflict, match="value_eu"):
        _items(s)
    assert _items(s, verify=False)  # without verification the earliest copy wins silently


@pytest.mark.unit
def test_replay_until_and_determinism(store):
    first = _items(store)
    again = _items(store)
    assert len(first) == len(again)
    for x, y in zip(first, again, strict=True):
        assert type(x) is type(y)
        if isinstance(x, ReplayBatch):
            assert x.table.equals(y.table, check_metadata=True) and x.t_ingest == y.t_ingest
        else:
            assert x == y
    cut = _items(store, until=E + 3 * H)
    assert {i.t_ingest for i in cut} == {E + 2 * H, E + 3 * H}
    assert all(
        pc.max(i.table.column("t_ingest")).as_py() <= E + 3 * H for i in cut if isinstance(i, ReplayBatch)
    )


@pytest.mark.unit
def test_replay_consumer_view_hides_restricted_data(tmp_path):
    s = ParquetStore.at(tmp_path, C)
    manifests = example_records(C, "sortie.manifest", 2)
    s.write("sortie.manifest", manifests)
    s.write("labels.truth", example_records(C, "labels.truth", 2))
    with pytest.raises(PermissionError):
        ReplayStreamer(s, ["labels.truth"])
    batches = [i for i in ReplayStreamer(s) if isinstance(i, ReplayBatch)]
    assert {b.topic for b in batches} == {"sortie.manifest"}
    for b in batches:
        assert "root_seed" not in b.table.schema.names
        assert b.table.schema.equals(C.consumer_schema("sortie.manifest"), check_metadata=True)
    val = [
        i for i in ReplayStreamer(s, ["sortie.manifest"], audience="validation") if isinstance(i, ReplayBatch)
    ]
    assert all("root_seed" in b.table.schema.names for b in val)
    # the validation audience gets the real restricted values back, joined by record_id
    joined = {r["record_id"]: r["root_seed"] for b in val for r in b.table.to_pylist()}
    assert joined == dict(
        zip(manifests.column("record_id").to_pylist(), manifests.column("root_seed").to_pylist(), strict=True)
    )
    with pytest.raises(ValueError, match="no ingest time"):
        ReplayStreamer(s, ["labels.truth"], audience="validation")


def _has_dup(t: pa.Table) -> bool:
    return bool(pc.any(pc.not_equal(pc.bit_wise_and(t.column("quality_flags"), DUP), 0)).as_py())


@pytest.mark.unit
@pytest.mark.parametrize("order", ["early first", "late first"])
def test_dedup_keeps_the_earliest_ingest_whatever_the_row_order(order):
    """Direct unit test of the rule: the earliest-ingested copy of a record_id survives (n = 30 + 30 rows)."""
    from phalanx.streaming import dedup_by_record_id

    early, late = _samples("T001", "A", E + 4 * H), _samples("T001", "A", E + 6 * H, dup=True)
    both = pa.concat_tables([early, late] if order == "early first" else [late, early])
    kept, dropped = dedup_by_record_id(C, "param.samples", both)
    assert (kept.num_rows, dropped) == (30, 30)
    assert set(kept.column("t_ingest").to_pylist()) == {E + 4 * H}
    assert not _has_dup(kept)


@pytest.mark.unit
def test_earliest_ingest_wins_in_read_replay_and_as_of(tmp_path):
    """A full re-download (later t_ingest, DUPLICATE_DOWNLOAD set) is written *before* the original, so file
    order cannot help: read, replay and as_of must all deliver the earliest-ingested copy. A partial later
    download adds only its new records, with their own (later) ingest time."""
    from phalanx.streaming import ObservationView

    s = ParquetStore(tmp_path, C)
    s.write("param.samples", _samples("T001", "A", E + 6 * H, dup=True), date="2026-10-03")
    s.write("param.samples", _samples("T001", "A", E + 4 * H), date="2026-10-03")
    s.write("param.samples", _samples("T001", "A", E + 5 * H, n=12, dup=True), date="2026-10-03")  # 6 new
    r = s.read("param.samples")
    assert r.num_rows == 36
    assert sorted(set(r.column("t_ingest").to_pylist())) == [E + 4 * H, E + 5 * H]
    assert pc.sum(pc.equal(r.column("t_ingest"), E + 4 * H)).as_py() == 30
    batches = [i for i in _items(s) if isinstance(i, ReplayBatch)]
    assert [(b.t_ingest, b.table.num_rows) for b in batches] == [(E + 4 * H, 30), (E + 5 * H, 6)]
    assert not _has_dup(batches[0].table)
    view = ObservationView(s)
    assert view.as_of(E + 3 * H, "param.samples").num_rows == 0
    for t, expected in ((E + 4 * H, {E + 4 * H}), (E + 7 * H, {E + 4 * H, E + 5 * H})):
        got = view.as_of(t, "param.samples")
        assert set(got.column("t_ingest").to_pylist()) == expected
        assert pc.sum(pc.equal(got.column("t_ingest"), E + 4 * H)).as_py() == 30
