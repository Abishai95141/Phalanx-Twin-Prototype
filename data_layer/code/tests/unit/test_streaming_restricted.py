"""R1 (coordinator review): restricted data is physically separated from the consumer tree (invariant I5).

- R1a: restricted topics and restricted fields are written only under the restricted root; the consumer tree
  holds no restricted column, value or metadata.
- R1b: every read API defaults to the consumer audience; validation must be requested and needs the
  restricted root.
- R1c: leak test. All 10 topics are written through the normal path with distinctive secret values (seed,
  stream-table key path, truth values from the fast path and from labels), then every file of the consumer
  tree is audited by name, metadata, raw bytes and decoded values. Positive control: the same audit finds the
  secrets in the restricted tree (they really were written, and zstd does not hide them from the audit).
  Negative controls: four planted leaks are each caught.
- R1d: ReplayStreamer and ObservationView touch only the consumer tree unless validation is requested.

Sample: EXAMPLE records, 4 per topic, plus one EXAMPLE CIR batch (3 streams x 6 samples, 18 truth values).
"""

from __future__ import annotations

from pathlib import Path

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq
import pytest

from phalanx.dictionary.contract import load_contract
from phalanx.dictionary.contract.examples import example_records
from phalanx.ground import FastPathConfig, cir_to_param_samples, cir_to_truth_labels
from phalanx.ground.examples import example_cir_batch, example_units
from phalanx.ground.rid import record_ids
from phalanx.streaming import (
    CONSUMER,
    RESTRICTED,
    ObservationView,
    ParquetStore,
    ReplayBatch,
    ReplayStreamer,
    StoreError,
    audit_consumer_tree,
    parquet_bytes,
    project_consumer,
)

C = load_contract("v0")
E = 1_791_000_000 * 10**9
H = 3600 * 10**9
SEED = "c0ffee00" * 4
KEY_PATH = "scenario=s:LEAKSCN/tail=s:X0/subsystem=s:acquisition"
STREAM_REF = "f00dfeed" * 4
SECRET_SUBJECT = "SECRETHIDDENSTATE"
SECRET_CATEGORY = "SECRETFAULTMODE"
LABEL_VALUE = 271828.182845
# restricted truth instants that coincide with no consumer time (consumer example times sit on whole ms)
T_TRUE_SECRET = [E + 123_456_789 + i for i in range(4)]


def _set(table: pa.Table, name: str, values: list) -> pa.Table:
    i = table.schema.get_field_index(name)
    f = table.schema.field(i)
    return table.set_column(i, f, pa.array(values, f.type))


def _write_everything(store: ParquetStore) -> list:
    """Write all 10 topics through the normal path; return the secret values that went to restricted data."""
    secrets: list = [SEED, KEY_PATH, STREAM_REF, SECRET_SUBJECT, SECRET_CATEGORY]
    for topic in C.topic_names:
        t = example_records(C, topic, 4)
        if topic == "sortie.manifest":
            t = _set(t, "root_seed", [SEED] * 4)
            t = _set(t, "rng_stream_table", [[{"key_path": KEY_PATH, "stream_ref": STREAM_REF}]] * 4)
        if topic == "labels.truth":
            t = _set(t, "value", [LABEL_VALUE + i for i in range(4)])
            t = _set(t, "subject_id", [SECRET_SUBJECT] * 4)
            t = _set(t, "category", [SECRET_CATEGORY] * 4)
            t = _set(_set(t, "t_true", T_TRUE_SECRET), "t_end", [None] * 4)
            key = {k.name: t.column(k.name) for k in C.topics[topic].record_id_key}
            t = _set(t, "record_id", record_ids(C, topic, key, 4).to_pylist())
            secrets += [LABEL_VALUE + i for i in range(4)] + t.column("record_id").to_pylist() + T_TRUE_SECRET
        store.write(topic, t)
    batch = example_cir_batch("T001", "T001-S1", E, 6)
    cfg = FastPathConfig("0.1.0", "ab" * 32, example_units())
    store.write("param.samples", cir_to_param_samples(batch, cfg, t_ingest=E + 2 * H), date="2026-10-03")
    labels = cir_to_truth_labels(batch, cfg)
    store.write("labels.truth", labels, date="2026-10-03")
    secrets += batch.table.column("truth_value").to_pylist() + labels.column("record_id").to_pylist()
    return secrets


@pytest.mark.unit
def test_r1c_consumer_tree_holds_no_restricted_data(tmp_path):
    store = ParquetStore.at(tmp_path, C)
    secrets = _write_everything(store)
    # R1a: layout
    consumer_topics = {p.name for p in store.root.iterdir()}
    restricted_topics = {p.name for p in store.restricted_root.iterdir()}
    assert "labels.truth" not in consumer_topics and "labels.truth" in restricted_topics
    assert "sortie.manifest" in consumer_topics and "sortie.manifest" in restricted_topics
    assert restricted_topics == {"labels.truth", "sortie.manifest"}
    # R1c: the audit finds nothing in the consumer tree ...
    assert audit_consumer_tree(store.root, C, secrets=secrets) == []
    # ... and is not blind: the same audit sees the secrets in the restricted tree (positive control)
    found = audit_consumer_tree(store.restricted_root, C, secrets=secrets)
    assert any("decoded values contain secrets" in f for f in found)
    assert any("restricted field 'root_seed'" in f for f in found)
    assert any("restricted topic" in f or "labels.truth" in f for f in found)
    # every consumer file has the consumer schema exactly
    for topic in C.topic_names:
        for f in store.files(topic, tree=CONSUMER):
            assert pq.read_schema(f).equals(C.consumer_schema(topic), check_metadata=True)


def _consumer_dir(store: ParquetStore, topic: str) -> Path:
    d = store.root / topic / "date=2026-10-03" / "tail_no=X0" / "sortie_id=X0"
    d.mkdir(parents=True, exist_ok=True)
    return d


@pytest.mark.unit
@pytest.mark.parametrize(
    "leak",
    [
        "restricted column",
        "truth value in a consumer column",
        "t_true instants in t_utc",
        "seed in metadata",
        "restricted topic",
    ],
)
def test_r1c_planted_leaks_are_caught(tmp_path, leak):
    store = ParquetStore.at(tmp_path, C)
    secrets = _write_everything(store)
    assert audit_consumer_tree(store.root, C, secrets=secrets) == []
    if leak == "restricted column":
        t = _set(example_records(C, "sortie.manifest", 2), "root_seed", [SEED, SEED])
        pq.write_table(t, _consumer_dir(store, "sortie.manifest") / "part-planted.parquet")
        expect = "restricted field 'root_seed'"
    elif leak == "truth value in a consumer column":
        t = project_consumer(C, "param.samples", example_records(C, "param.samples", 2))
        t = _set(t, "value_eu", [LABEL_VALUE, 1.0])  # zstd-compressed: invisible to a raw byte scan
        (_consumer_dir(store, "param.samples") / "part-planted.parquet").write_bytes(parquet_bytes(t))
        expect = "decoded values contain secrets"
    elif leak == "t_true instants in t_utc":  # integer secrets in an int64 time column (verifier's plant)
        t = project_consumer(C, "param.samples", example_records(C, "param.samples", 2))
        t = _set(t, "t_utc", T_TRUE_SECRET[:2])
        (_consumer_dir(store, "param.samples") / "part-planted.parquet").write_bytes(parquet_bytes(t))
        expect = "column 't_utc' decoded values contain secrets (strings 0, ints 2"
    elif leak == "seed in metadata":
        t = project_consumer(C, "param.samples", example_records(C, "param.samples", 2))
        t = t.replace_schema_metadata({**t.schema.metadata, b"note": SEED.encode()})
        pq.write_table(t, _consumer_dir(store, "param.samples") / "part-planted.parquet")
        expect = "metadata contains a secret value"
    else:
        t = example_records(C, "labels.truth", 2)
        pq.write_table(t, _consumer_dir(store, "labels.truth") / "part-planted.parquet")
        expect = "labels.truth"
    findings = audit_consumer_tree(store.root, C, secrets=secrets)
    assert any(expect in f for f in findings), findings


@pytest.mark.unit
def test_r1b_reads_default_to_the_consumer_audience(tmp_path):
    store = ParquetStore.at(tmp_path, C)
    _write_everything(store)
    m = store.read("sortie.manifest")
    assert "root_seed" not in m.schema.names
    assert m.schema.equals(C.consumer_schema("sortie.manifest"), check_metadata=True)
    with pytest.raises(PermissionError):
        store.read("labels.truth")
    full = store.read("sortie.manifest", audience="validation")
    assert set(full.column("root_seed").to_pylist()) == {SEED}
    for item in ReplayStreamer(store):  # default audience
        if isinstance(item, ReplayBatch):
            assert item.table.schema.equals(C.consumer_schema(item.topic), check_metadata=True)
    view = ObservationView(store)  # default audience
    assert "root_seed" not in view.as_of(E + 10 * H, "sortie.manifest").schema.names
    with pytest.raises(PermissionError):
        view.as_of(E + 10 * H, "labels.truth")
    with pytest.raises(ValueError):
        store.read("param.samples", audience="everything")


@pytest.mark.unit
def test_r1a_consumer_only_store_cannot_write_or_read_restricted_data(tmp_path):
    consumer_only = ParquetStore(tmp_path / "consumer", C)  # no restricted root
    with pytest.raises(PermissionError):
        consumer_only.write("labels.truth", example_records(C, "labels.truth", 2))
    with pytest.raises(PermissionError, match="restricted values"):
        consumer_only.write(
            "sortie.manifest", _set(example_records(C, "sortie.manifest", 2), "root_seed", [SEED] * 2)
        )
    # a manifest whose restricted fields are all null carries no secret and may be written consumer-side
    m = example_records(C, "sortie.manifest", 2)
    m = _set(_set(m, "root_seed", [None, None]), "rng_stream_table", [None, None])
    assert consumer_only.write("sortie.manifest", m)
    with pytest.raises(PermissionError):
        consumer_only.read("sortie.manifest", audience="validation")
    with pytest.raises(StoreError, match="outside"):
        ParquetStore(tmp_path / "x", C, restricted_root=tmp_path / "x" / "restricted")
    with pytest.raises(StoreError, match="outside"):
        ParquetStore(tmp_path / "y" / "consumer", C, restricted_root=tmp_path / "y")


class _SpyStore(ParquetStore):
    """Test-only boundary spy: records which tree every file read touches."""

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.trees: list[str] = []

    def read_file(self, topic, path, *, tree=CONSUMER):
        self.trees.append(tree)
        return super().read_file(topic, path, tree=tree)

    def files(self, topic, *, tree=CONSUMER, **kw):
        self.trees.append(tree)
        return super().files(topic, tree=tree, **kw)


@pytest.mark.unit
def test_r1d_replay_and_as_of_touch_only_the_consumer_tree(tmp_path):
    ParquetStore.at(tmp_path, C).write(
        "sortie.manifest", _set(example_records(C, "sortie.manifest", 2), "root_seed", [SEED] * 2)
    )
    spy = _SpyStore(tmp_path / CONSUMER, C, restricted_root=tmp_path / RESTRICTED)
    list(ReplayStreamer(spy))
    view = ObservationView(spy)
    view.as_of(E + 10 * H, "sortie.manifest")
    view.ingested(E + 10 * H, [bytes(16)])
    assert spy.trees and set(spy.trees) == {CONSUMER}
    spy.trees.clear()
    val = [
        i
        for i in ReplayStreamer(spy, ["sortie.manifest"], audience="validation")
        if isinstance(i, ReplayBatch)
    ]
    assert RESTRICTED in spy.trees  # validation is the only way in, and it is explicit
    assert all(pc.all(pc.equal(b.table.column("root_seed"), SEED)).as_py() for b in val)


@pytest.mark.unit
def test_r1c_small_integer_secrets_are_refused(tmp_path):
    """A small int would match ordinary counts and flags: the audit refuses it rather than skip it."""
    with pytest.raises(ValueError, match="below"):
        audit_consumer_tree(tmp_path, C, secrets=[42])
    with pytest.raises(ValueError, match="unsupported"):
        audit_consumer_tree(tmp_path, C, secrets=[True])
    assert audit_consumer_tree(tmp_path / "missing", C, secrets=[E]) == []
