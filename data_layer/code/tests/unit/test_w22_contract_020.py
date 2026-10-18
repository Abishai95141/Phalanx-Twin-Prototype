"""W2.2 item 4 (acceptance A5): contract 0.2.0 is an additive minor version of the frozen 0.1.0.

- 0.1.0 stays loadable by its semver with its frozen identity (hash 18d7627b...); ``v0`` is 0.2.0;
- the only change is two nullable fields appended to ``param.samples`` (``recording_id``, ``sink``) and the
  full-path record-id rule for an identified recording (A-W0.4-22), checked by ``migrate.additive_changes``
  with negative controls (a removed, retyped or non-nullable field is refused);
- 0.1.0 consumers still pass: a 0.2.0 fast-path table projected to 0.1.0 equals the fast path run under 0.1.0,
  byte for byte, and a 0.1.0 table upgrades back to the 0.2.0 one;
- record ids of everything 0.1.0 could produce are unchanged; a non-null recording id qualifies the full-path
  channel component, so two recordings of one sortie never collide.

Sample: deterministic EXAMPLE CIR (``ground.examples``, 2 streams x 12 samples) for the fast path; contract
records built from components for the record-id rules. The full-path runs (n = 1 fixture sortie) are in
``tests/integration/test_w22_contract_020_full_path.py``.
"""

from __future__ import annotations

import shutil

import pyarrow as pa
import pytest

from phalanx.dictionary.contract import load_contract, load_spec_dir
from phalanx.dictionary.contract.loader import SPEC_ROOT
from phalanx.ground.examples import example_cir_batch, example_units
from phalanx.ground.fast_path import FastPathConfig, cir_to_param_samples
from phalanx.ground.migrate import ContractMigrationError, additive_changes, project, upgrade
from phalanx.ground.rid import check_recording_identity, full_path_channel_id, record_ids
from phalanx.streaming import ParquetStore
from phalanx.streaming.parquet_store import StoreError

C010 = load_contract("0.1.0")
C020 = load_contract("0.2.0")
FROZEN_010 = "18d7627ba6f0f9b694c1978bd4c6cad65f62fea8fd4e8fcb537801c8cf57cc4e"
CFG = FastPathConfig("0.1.2", "ab" * 32, example_units())
EPOCH = 1_790_000_000 * 10**9


def _batch():
    """EXAMPLE CIR (3 streams x 12 samples), not physics."""
    return example_cir_batch("KH2001", "KH2001-20260921-0900", EPOCH, 12)


@pytest.mark.unit
def test_versions_and_frozen_identity():
    assert C010.version == "0.1.0" and C010.status == "frozen" and C010.hash == FROZEN_010
    assert C020.version == "0.2.0" and load_contract("v0") is C020
    assert C020.status == "frozen"  # frozen by the owner (AD-56)


@pytest.mark.unit
def test_the_change_is_additive_and_only_param_samples_grows():
    assert additive_changes(C010, C020) == {"param.samples": ("recording_id", "sink")}
    s = C020.schemas["param.samples"]
    assert s.names[: len(C010.schemas["param.samples"].names)] == C010.schemas["param.samples"].names
    for name in ("recording_id", "sink"):
        assert s.field(name).nullable and s.field(name).type == pa.string()
    for t in C010.topic_names:
        if t != "param.samples":
            assert C020.schemas[t].remove_metadata().equals(C010.schemas[t].remove_metadata()), t


def _edited(tmp_path, file: str, old: str, new: str):
    d = tmp_path / "v0"
    shutil.copytree(SPEC_ROOT / "v0", d)
    p = d / file
    text = p.read_text(encoding="utf-8")
    assert old in text
    p.write_text(text.replace(old, new, 1), encoding="utf-8")
    return load_spec_dir(d)


@pytest.mark.unit
@pytest.mark.parametrize(
    ("file", "old", "new", "why"),
    [
        ("topics/param.samples.yaml", "  - name: raw_counts\n", "  - name: raw_count\n", "renamed"),
        (
            "topics/param.samples.yaml",
            "  - name: recording_id\n    type: string\n    nullable: true",
            "  - name: recording_id\n    type: string\n    nullable: false",
            "non-nullable",
        ),
        (
            "topics/param.samples.yaml",
            "  - name: raw_counts\n    type: int64",
            "  - name: raw_counts\n    type: float64",
            "retyped",
        ),
        ("contract.yaml", "{name: BUS_INVALID,", "{name: BUS_INVALID_X,", "enum symbol renamed"),
    ],
)
def test_breaking_edits_are_refused(tmp_path, file, old, new, why):
    """Negative controls: what a minor version may not do."""
    bad = _edited(tmp_path, file, old, new)
    with pytest.raises(ContractMigrationError):
        additive_changes(C010, bad)


@pytest.mark.unit
def test_versions_must_increase_within_the_line():
    with pytest.raises(ContractMigrationError):
        additive_changes(C020, C010)
    with pytest.raises(ContractMigrationError):
        additive_changes(C020, C020)


@pytest.mark.unit
def test_0_1_0_consumers_still_pass_on_the_fast_path():
    batch = _batch()
    t_ingest = int(batch.table.column("t_sample").to_numpy().max()) + 3600 * 10**9
    new = cir_to_param_samples(batch, CFG, t_ingest=t_ingest, contract=C020)
    old = cir_to_param_samples(batch, CFG, t_ingest=t_ingest, contract=C010)
    assert new.column("recording_id").null_count == new.num_rows == new.column("sink").null_count
    assert project(new, C020, C010, "param.samples").equals(old, check_metadata=True)
    assert upgrade(old, C010, C020, "param.samples").equals(new, check_metadata=True)
    # identical record ids: the 0.1.0 identity of every fast-path record is kept
    assert new.column("record_id").equals(old.column("record_id"))


@pytest.mark.unit
def test_stores_are_bound_to_their_contract_and_the_projection_bridges_them(tmp_path):
    batch = _batch()
    t_ingest = int(batch.table.column("t_sample").to_numpy().max()) + 3600 * 10**9
    new = cir_to_param_samples(batch, CFG, t_ingest=t_ingest, contract=C020)
    s020 = ParquetStore.at(tmp_path / "s020", C020)
    s020.write("param.samples", new, date="2026-10-15")
    assert s020.read("param.samples").num_rows == new.num_rows
    # a 0.1.0 reader refuses 0.2.0 files (A-W0.4-19) ...
    with pytest.raises(StoreError):
        ParquetStore(tmp_path / "s020" / "consumer", C010).read("param.samples")
    # ... and reads the explicit projection
    s010 = ParquetStore.at(tmp_path / "s010", C010)
    s010.write("param.samples", project(new, C020, C010, "param.samples"), date="2026-10-15")
    got = s010.read("param.samples")
    assert sorted(got.column("record_id").to_pylist()) == sorted(new.column("record_id").to_pylist())


def _ids(contract, channel_ids):
    n = len(channel_ids)
    return record_ids(
        contract,
        "param.samples",
        {
            "provenance": "full_path",
            "tail_no": "KH2001",
            "sortie_id": "KH2001-20260921-0900",
            "channel_id": pa.array(channel_ids, pa.string()),
            "param_id": "ENG.N2",
            "seq": pa.array(list(range(n)), pa.uint64()),
            "msg_index": 0,
        },
        n,
    ).to_pylist()


@pytest.mark.unit
def test_record_id_rule_keeps_0_1_0_ids_and_separates_recordings():
    bare = [full_path_channel_id(3, None) for _ in range(4)]
    assert bare == ["3"] * 4
    assert _ids(C010, bare) == _ids(C020, bare)  # same components, same ids under both versions
    cdr = [full_path_channel_id(3, "CDR-1") for _ in range(4)]
    ecms = [full_path_channel_id(3, "ECMS_HUMS-1") for _ in range(4)]
    assert cdr[0] == "CDR-1:3"
    ids = [_ids(C020, x) for x in (bare, cdr, ecms)]
    assert len({r for x in ids for r in x}) == 12  # same channel/seq/msg in three recordings: no collision


@pytest.mark.unit
@pytest.mark.parametrize(
    ("rec", "sink"),
    [("CDR-1", None), (None, "CDR"), ("CDR:1", "CDR"), ("CDR-1", "cdr"), ("", "CDR")],
)
def test_recording_identity_rules_are_enforced(rec, sink):
    with pytest.raises(ValueError):
        check_recording_identity(rec, sink)


@pytest.mark.unit
def test_contract_validation_rejects_a_malformed_sink():
    batch = _batch()
    t_ingest = int(batch.table.column("t_sample").to_numpy().max()) + 3600 * 10**9
    t = cir_to_param_samples(batch, CFG, t_ingest=t_ingest, contract=C020)
    n = t.num_rows
    bad = t.set_column(
        t.schema.get_field_index("sink"), C020.schemas["param.samples"].field("sink"), pa.array(["cdr"] * n)
    )
    from phalanx.dictionary.contract import ContractViolation

    with pytest.raises(ContractViolation):
        C020.validate("param.samples", bad)
