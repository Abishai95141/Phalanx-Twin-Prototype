"""W0.4 A7 (fast path) and deliverable 5: CIR -> param.samples, validated against the generated schema.

Sample: EXAMPLE batch, 3 streams x 8 samples (n = 24): redundant lanes A/B plus a simplex stream, the smallest
batch that exercises the channel rule, the lane-null case and per-stream sample indices.
"""

from __future__ import annotations

import pyarrow as pa
import pyarrow.compute as pc
import pytest

from phalanx.dictionary.contract import ContractViolation, load_contract
from phalanx.ground import (
    CirBatch,
    CirViolation,
    FastPathConfig,
    cir_to_param_samples,
    cir_to_truth_labels,
    record_id,
)
from phalanx.ground.examples import example_cir_batch, example_units

C = load_contract("v0")
EPOCH = 1_791_000_000 * 10**9
INGEST = EPOCH + 4 * 3600 * 10**9
CFG = FastPathConfig("0.1.0", "ab" * 32, example_units(), {"ENG.N2": "E404-0001", "ENG.EGT": "E404-0001"})


def _batch(n: int = 8) -> CirBatch:
    return example_cir_batch("T001", "T001-S1", EPOCH, n)


@pytest.mark.unit
def test_a7_fast_path_output_is_the_contract_schema():
    out = cir_to_param_samples(_batch(), CFG, t_ingest=INGEST)
    assert out.schema.equals(C.schemas["param.samples"], check_metadata=True)
    C.validate("param.samples", out)
    assert out.num_rows == 24


@pytest.mark.unit
def test_fast_path_time_and_null_rules():
    """Exposes the fast-path PROXY (A-W0.4-4): no bus/recorder model, t_utc is a perfect time source."""
    b = _batch()
    out = cir_to_param_samples(b, CFG, t_ingest=INGEST)
    for name in ("t_bus", "t_record", "raw_counts", "bus", "rt_sa_word", "label_sdi"):
        assert out.column(name).null_count == out.num_rows, name
    assert out.column("t_utc").equals(out.column("t_sample"))
    assert pc.all(pc.equal(out.column("t_ingest"), INGEST)).as_py()
    assert set(out.column("provenance").to_pylist()) == {"direct"}
    # the limitation: a fast-path record can never show time-source loss or bus/recorder artefacts
    non_acq = C.quality_flags.scope_mask("bus", "recorder", "ground")
    assert not pc.any(
        pc.not_equal(pc.bit_wise_and(out.column("quality_flags"), pa.scalar(non_acq, pa.uint32())), 0)
    ).as_py()
    # values pass through unchanged; truth and t_true never enter the contract
    assert out.column("value_eu").to_pylist() == b.table.column("value").to_pylist()
    assert "truth_value" not in out.schema.names and "t_true" not in out.schema.names
    assert set(out.column("units").to_pylist()) == {"%", "degC"}
    assert set(out.column("engine_serial").to_pylist()) == {"E404-0001"}


@pytest.mark.unit
def test_fast_path_record_ids_follow_the_documented_rule():
    b = _batch()
    out = cir_to_param_samples(b, CFG, t_ingest=INGEST)
    for row, rid in zip(b.table.to_pylist(), out.column("record_id").to_pylist(), strict=True):
        expect = record_id(
            C,
            "param.samples",
            {
                "provenance": "direct",
                "tail_no": "T001",
                "sortie_id": "T001-S1",
                "channel_id": f"direct:{row['source_lru']}:{row['lane'] or ''}",
                "param_id": row["param_id"],
                "seq": row["sample_index"],
                "msg_index": 0,
            },
        )
        assert rid == expect


@pytest.mark.unit
def test_fast_path_deterministic_and_row_order_independent():
    b = _batch()
    a = cir_to_param_samples(b, CFG, t_ingest=INGEST)
    a2 = cir_to_param_samples(b, CFG, t_ingest=INGEST)
    assert a.equals(a2, check_metadata=True)
    rev = CirBatch(b.tail_no, b.sortie_id, b.table.take(pa.array(list(reversed(range(b.table.num_rows))))))
    r = cir_to_param_samples(rev, CFG, t_ingest=INGEST)
    key = [("t_sample", "ascending"), ("record_id", "ascending")]
    assert a.sort_by(key).equals(r.sort_by(key), check_metadata=True)
    # block-wise production (two halves with continuing sample_index) gives the same records as one batch
    h1 = example_cir_batch("T001", "T001-S1", EPOCH, 4)
    h2 = example_cir_batch("T001", "T001-S1", EPOCH, 4, first_index=4)
    parts = pa.concat_tables([cir_to_param_samples(h, CFG, t_ingest=INGEST) for h in (h1, h2)])
    assert parts.sort_by(key).equals(a.sort_by(key), check_metadata=True)


@pytest.mark.unit
def test_fast_path_rejects_bad_inputs():
    with pytest.raises(ValueError, match="t_ingest precedes"):
        cir_to_param_samples(_batch(), CFG, t_ingest=EPOCH)
    with pytest.raises(KeyError, match="no units"):
        cir_to_param_samples(_batch(), FastPathConfig("0.1.0", "ab" * 32, {"ENG.N2": "%"}), t_ingest=INGEST)
    with pytest.raises(TypeError):
        cir_to_param_samples(_batch(), CFG, t_ingest=float(INGEST))
    b = _batch()
    bad = CirBatch(b.tail_no, b.sortie_id, b.table.drop_columns(["rng_key_path"]))
    with pytest.raises(CirViolation):
        cir_to_param_samples(bad, CFG, t_ingest=INGEST)
    with pytest.raises(ContractViolation, match="dict_hash"):
        cir_to_param_samples(_batch(), FastPathConfig("0.1.0", "NOT-HEX", example_units()), t_ingest=INGEST)


@pytest.mark.unit
def test_a7_full_path_shaped_batch_uses_the_same_schema():
    """A full-path record (bus fields, RTC, raw word, recorder flags) validates against the same schema
    (AD-12)."""
    out = cir_to_param_samples(_batch(2), CFG, t_ingest=INGEST)
    n = out.num_rows
    cols = {name: out.column(name) for name in out.schema.names}
    cols["provenance"] = pa.array(["full_path"] * n)
    cols["bus"] = pa.array(["AV-MUX-2"] * n)
    cols["rt_sa_word"] = pa.array(["RT07/SA03/W01"] * n)
    cols["t_bus"] = pc.add(out.column("t_sample"), 2_000_000)
    cols["t_record"] = pa.array(list(range(100, 100 + n)), pa.int64())
    cols["raw_counts"] = pa.array([4096] * n, pa.int64())
    cols["quality_flags"] = pa.array([C.quality_flags.mask("TIME_SOURCE_INTERNAL")] * n, pa.uint32())
    full = pa.Table.from_arrays(
        [cols[f.name] for f in C.schemas["param.samples"]], schema=C.schemas["param.samples"]
    )
    C.validate("param.samples", full)


@pytest.mark.unit
def test_truth_goes_only_to_restricted_labels():
    b = _batch()
    # make lane B sample at exactly lane A's instants: the two lanes then share (param_id, t_true)
    t = b.table
    lanes = t.column("lane").to_pylist()
    ts, tt = t.column("t_sample").to_pylist(), t.column("t_true").to_pylist()
    a_rows = [i for i, x in enumerate(lanes) if x == "A"]
    b_rows = [i for i, x in enumerate(lanes) if x == "B"]
    for ia, ib in zip(a_rows, b_rows, strict=True):
        ts[ib], tt[ib] = ts[ia], tt[ia]
    t = t.set_column(
        t.schema.get_field_index("t_sample"), t.schema.field("t_sample"), pa.array(ts, pa.int64())
    )
    t = t.set_column(t.schema.get_field_index("t_true"), t.schema.field("t_true"), pa.array(tt, pa.int64()))
    b = CirBatch(b.tail_no, b.sortie_id, t)
    samples = cir_to_param_samples(b, CFG, t_ingest=INGEST)
    labels = cir_to_truth_labels(b, CFG)
    C.validate("labels.truth", labels)
    assert C.topics["labels.truth"].restricted
    assert labels.column("value").to_pylist() == b.table.column("truth_value").to_pylist()
    # every label points at the sample it labels; lanes A/B at equal t_true do not collide
    assert set(labels.column("related_record_id").to_pylist()) == set(samples.column("record_id").to_pylist())
    assert len(set(labels.column("record_id").to_pylist())) == labels.num_rows
    with pytest.raises(PermissionError):
        C.consumer_schema("labels.truth")
