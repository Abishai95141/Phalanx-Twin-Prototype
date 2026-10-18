"""W2.2 item 4 (A5) on the full path: contract 0.2.0 recording identity end to end (M16 -> download -> M17).

- the single bus-monitor capture (no recording identity, the W1.7 path) decodes to the 0.1.0 records: same
  record ids and values (the golden digest from before W2.2 minus the spare FTI slots' zero fill, W2.2 phase
  B; derived in test_w22_datapath_migrations), ``recording_id``/``sink`` null, and its projection validates
  under the frozen 0.1.0;
- an identified recording (``recording_id`` "CDR-1", sink CDR) has identical file bytes, fills both columns,
  and gets record ids disjoint from the unidentified one, so two recordings of one sortie (same Ch10 channel
  IDs and packet counts) never collide in an idempotent store; the restricted truth labels still join;
- the fast and full paths keep one schema (AD-12).

Sample: the W1.7 fixture sortie (6 s, every recorded-bus channel; 45,140 records per delivery), decoded twice
(n = 2 runs): the smallest input on which every channel ID and record-id component appears.
"""

from __future__ import annotations

import numpy as np
import pyarrow as pa
import pytest
from test_bus_cir_fixture import IDENT, make_cir
from test_decoder_full_path import T0, T1, _run
from test_w22_datapath_migrations import GOLDEN_RECORDS_B, records_digest

from phalanx.dictionary import load_dictionary
from phalanx.dictionary.contract import load_contract
from phalanx.ground.fast_path import FastPathConfig, cir_to_param_samples
from phalanx.ground.migrate import project
from phalanx.recorder.full_path import full_path_truth_labels
from phalanx.streaming import ParquetStore

C020 = load_contract("0.2.0")
C010 = load_contract("0.1.0")


@pytest.fixture(scope="module")
def cir():
    return make_cir(None, T0 - 10**9, T1, invalid_every=11)


@pytest.fixture(scope="module")
def plain(cir):
    return _run(cir)


@pytest.fixture(scope="module")
def cdr(cir):
    return _run(cir, recording_id="CDR-1", sink="CDR")


@pytest.mark.integration
def test_unidentified_capture_keeps_the_0_1_0_records(plain):
    s = plain.decoded[1].samples
    assert s.schema.equals(C020.schemas["param.samples"], check_metadata=True)
    assert records_digest(s) == GOLDEN_RECORDS_B and s.num_rows == 45_140
    assert s.column("recording_id").null_count == s.num_rows == s.column("sink").null_count
    old = project(s, C020, C010, "param.samples")
    assert old.schema.equals(C010.schemas["param.samples"], check_metadata=True)


@pytest.mark.integration
def test_identified_recording_fills_the_identity_and_separates_record_ids(plain, cdr):
    assert cdr.recording.data == plain.recording.data  # the label is ground metadata, not file content
    a, b = plain.decoded[1].samples, cdr.decoded[1].samples
    assert a.num_rows == b.num_rows
    assert set(b.column("recording_id").to_pylist()) == {"CDR-1"} and set(b.column("sink").to_pylist()) == {
        "CDR"
    }
    for name in ("param_id", "value_eu", "raw_counts", "t_sample", "t_record", "validity", "quality_flags"):
        assert a.column(name).equals(b.column(name)), name
    ids_a = set(a.column("record_id").to_pylist())
    ids_b = set(b.column("record_id").to_pylist())
    assert len(ids_a) == len(ids_b) == a.num_rows and not ids_a & ids_b
    # every delivery of the identified recording carries it (re-downloads keep their ids)
    for dec in cdr.decoded:
        assert set(dec.samples.column("sink").to_pylist()) == {"CDR"}
    assert set(cdr.decoded[2].samples.column("record_id").to_pylist()) == ids_b


@pytest.mark.integration
def test_truth_labels_join_the_identified_recording(cir, cdr):
    labels = full_path_truth_labels(cdr.recording, cir, contract=C020)
    related = set(labels.column("related_record_id").to_pylist())
    assert related and related <= set(cdr.decoded[1].samples.column("record_id").to_pylist())


@pytest.mark.integration
def test_two_recordings_of_one_sortie_coexist_in_one_store(tmp_path, plain, cdr):
    store = ParquetStore.at(tmp_path, C020)
    both = pa.concat_tables([plain.decoded[1].samples, cdr.decoded[1].samples])
    store.write("param.samples", both, date="2026-09-21")
    got = store.read("param.samples", tail_no=IDENT.tail_no, sortie_id=IDENT.sortie_id)
    assert got.num_rows == both.num_rows
    assert len(set(got.column("record_id").to_pylist())) == both.num_rows


@pytest.mark.integration
def test_fast_and_full_path_keep_one_schema(cir, plain):
    d = load_dictionary()
    fast = cir_to_param_samples(
        cir, FastPathConfig.from_dictionary(d, engine_serial=IDENT.engine_serial), t_ingest=T1 + 3600 * 10**9
    )
    assert fast.schema.equals(plain.decoded[1].samples.schema, check_metadata=True)
    assert fast.column("recording_id").null_count == fast.num_rows


@pytest.mark.integration
def test_identity_rules_are_checked_at_the_recorder(cir):
    with pytest.raises(ValueError, match="both null or both set"):
        _run(cir, recording_id="CDR-1")
    with pytest.raises(ValueError, match="does not match"):
        _run(cir, recording_id="CDR:1", sink="CDR")


@pytest.mark.integration
def test_digest_helper_is_order_and_value_sensitive(plain):
    """Negative control for the golden digest: a reordering or a one-LSB change of one record shows."""
    s = plain.decoded[1].samples
    rev = s.take(pa.array(np.arange(s.num_rows - 1, -1, -1)))
    assert records_digest(rev) != records_digest(s)
    v = s.column("value_eu").to_numpy().copy()
    v[17] += 1e-9
    bumped = s.set_column(s.schema.get_field_index("value_eu"), s.schema.field("value_eu"), pa.array(v))
    assert records_digest(bumped) != records_digest(s)
